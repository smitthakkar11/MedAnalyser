"""Build the condition knowledge base.

Merges two sources into one reviewable file:

* **Descriptions** from the Disease Symptom Description Dataset (CC BY-SA 4.0),
  which are encyclopedic and usable as-is.
* **Curated content** below — general treatment approaches, medication classes
  and questions to ask a doctor.

The dataset's `symptom_precaution.csv` is deliberately **not** used. An audit of
it found entries that this project must never show: "stop taking drug" for Drug
Reaction, "take radioactive iodine treatment" for hyperthyroidism, "take otc
pain reliver", several unevidenced folk remedies, and "salt baths" for
hypertension. Instructing someone to start or stop medication is exactly what
the brief rules out.

Run from the repository root::

    python -m ml.knowledge.build_condition_knowledge

The committed output is what a clinician would review, so it is generated once
and checked in rather than assembled at runtime.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = REPO_ROOT / "ml" / "data" / "raw"
OUTPUT = (
    REPO_ROOT / "backend" / "app" / "services" / "knowledge" / "data" / "condition_knowledge.json"
)

DESCRIPTION_SOURCE = "Disease Symptom Description Dataset (CC BY-SA 4.0)"
DESCRIPTION_URL = (
    "https://www.kaggle.com/datasets/itachi9604/disease-symptom-description-dataset"
)

#: Questions worth asking about almost anything, appended to every condition.
UNIVERSAL_QUESTIONS = [
    "What do you think is causing this, and what else could it be?",
    "Are there any tests that would help confirm it?",
    "What should make me come back or seek urgent care?",
]

#: condition -> (general treatment approaches, medication classes, extra questions)
CURATED: dict[str, tuple[list[str], list[str], list[str]]] = {
    "Fungal infection": (
        ["Keeping the affected area clean and dry.", "Topical or oral antifungal treatment, depending on site and extent."],
        ["antifungal", "topical_skin"],
        ["Is this likely to spread to others in my household?"],
    ),
    "Allergy": (
        ["Identifying and avoiding the trigger where possible.", "Symptom relief while exposure continues."],
        ["antihistamine", "corticosteroid"],
        ["Should I be tested to identify the trigger?", "Do I need an adrenaline auto-injector?"],
    ),
    "GERD": (
        ["Dietary and lifestyle adjustments such as meal timing and trigger foods.", "Medicines that reduce stomach acid."],
        ["antacid_ppi"],
        ["How long should I expect to stay on treatment?", "Do I need an endoscopy?"],
    ),
    "Chronic cholestasis": (
        ["Investigating the underlying cause of impaired bile flow.", "Managing itching and nutritional effects."],
        ["topical_skin"],
        ["What is causing the blockage or impairment?"],
    ),
    "Drug Reaction": (
        ["Identifying the medicine responsible, with the prescriber.", "Managing the reaction itself."],
        ["antihistamine", "corticosteroid"],
        ["Which medicine caused this, and what should be recorded on my allergy list?", "What alternatives are safe for me?"],
    ),
    "Peptic ulcer diseae": (
        ["Testing for Helicobacter pylori infection.", "Reducing stomach acid to allow healing."],
        ["antacid_ppi", "antibiotic"],
        ["Should I be tested for H. pylori?", "Are any of my current medicines contributing?"],
    ),
    "AIDS": (
        ["Specialist HIV care and antiretroviral therapy.", "Monitoring and preventing opportunistic infections."],
        ["antiviral"],
        ["How do I get referred to an HIV clinic?", "What monitoring will I need?"],
    ),
    "Diabetes": (
        ["Blood glucose monitoring and review.", "Diet, activity and weight management alongside medication where needed."],
        ["antidiabetic"],
        ["What should my target readings be?", "How often should I be reviewed?"],
    ),
    "Gastroenteritis": (
        ["Fluid replacement, which is the main priority.", "Usually self-limiting; antibiotics are rarely appropriate."],
        ["rehydration"],
        ["What signs of dehydration should I watch for?", "When should I come back if it does not settle?"],
    ),
    "Bronchial Asthma": (
        ["A personalised asthma action plan.", "Preventer and reliever inhalers, with technique checked."],
        ["bronchodilator", "corticosteroid"],
        ["Can you check my inhaler technique?", "What should I do if my reliever stops helping?"],
    ),
    "Hypertension": (
        ["Blood pressure monitoring over time rather than a single reading.", "Diet, activity, alcohol and salt reduction, alongside medication where indicated."],
        ["antihypertensive"],
        ["What is my target blood pressure?", "Should I monitor at home?"],
    ),
    "Migraine": (
        ["Identifying and managing triggers.", "Treatment for attacks, and preventive treatment if they are frequent."],
        ["analgesic"],
        ["Would preventive treatment be appropriate for me?", "Which pain relief is suitable given my other medicines?"],
    ),
    "Cervical spondylosis": (
        ["Posture, activity modification and physiotherapy.", "Pain management."],
        ["analgesic"],
        ["Would physiotherapy help?", "What symptoms would suggest nerve involvement?"],
    ),
    "Paralysis (brain hemorrhage)": (
        ["Emergency assessment and imaging.", "Rehabilitation, which usually begins early."],
        [],
        ["What rehabilitation is available?", "What can reduce the risk of this happening again?"],
    ),
    "Jaundice": (
        ["Finding the underlying cause, which determines everything else.", "Blood tests and often imaging of the liver and bile ducts."],
        [],
        ["What is causing the jaundice?", "Do I need liver imaging?"],
    ),
    "Malaria": (
        ["Prompt diagnosis by blood test.", "Treatment chosen according to the species and where it was acquired."],
        ["antimalarial"],
        ["Which type of malaria is it?", "Do I need to be treated in hospital?"],
    ),
    "Chicken pox": (
        ["Symptom relief, particularly for itching.", "Avoiding contact with people at higher risk while infectious."],
        ["antihistamine", "topical_skin", "analgesic"],
        ["How long am I infectious?", "Who around me is at higher risk?"],
    ),
    "Dengue": (
        ["Fluid balance and monitoring, which is the mainstay.", "Certain pain relievers are avoided in dengue — ask which are safe."],
        ["rehydration"],
        ["Which pain relief is safe for me with dengue?", "What warning signs should bring me back urgently?"],
    ),
    "Typhoid": (
        ["Confirmatory testing.", "Antibiotic treatment guided by local resistance patterns."],
        ["antibiotic", "rehydration"],
        ["Do I need to avoid preparing food for others?"],
    ),
    "hepatitis A": (
        ["Supportive care; it usually resolves without specific antiviral treatment.", "Avoiding alcohol and reviewing medicines processed by the liver."],
        ["vaccine"],
        ["Should my household be vaccinated?", "Which of my medicines affect the liver?"],
    ),
    "Hepatitis B": (
        ["Specialist assessment and monitoring.", "Antiviral treatment where indicated."],
        ["antiviral", "vaccine"],
        ["Do I need long-term monitoring?", "Should my household be tested or vaccinated?"],
    ),
    "Hepatitis C": (
        ["Specialist assessment; treatment is usually curative.", "Assessing the degree of liver involvement."],
        ["antiviral"],
        ["Am I eligible for antiviral treatment?"],
    ),
    "Hepatitis D": (
        ["Specialist care, as it occurs alongside hepatitis B.", "Monitoring liver function."],
        ["antiviral"],
        ["How does this change my hepatitis B treatment?"],
    ),
    "Hepatitis E": (
        ["Usually supportive care.", "Closer monitoring in pregnancy or existing liver disease."],
        [],
        ["Do I need liver monitoring?"],
    ),
    "Alcoholic hepatitis": (
        ["Stopping alcohol, which is the single most important step.", "Nutritional support and specialist liver review."],
        [],
        ["What support is available for stopping alcohol?", "How much liver damage is there?"],
    ),
    "Tuberculosis": (
        ["Confirmatory testing.", "A combination course over several months, with monitoring."],
        ["antitubercular"],
        ["How long is the course?", "Do my contacts need screening?"],
    ),
    "Common Cold": (
        ["Rest and fluids; it is self-limiting.", "Symptom relief only — antibiotics do not work on viruses."],
        ["analgesic"],
        ["When would this warrant coming back?"],
    ),
    "Pneumonia": (
        ["Assessment of severity, which decides home or hospital treatment.", "Antibiotics for bacterial pneumonia."],
        ["antibiotic", "analgesic"],
        ["Do I need a chest X-ray?", "What would mean I should be admitted?"],
    ),
    "Dimorphic hemmorhoids(piles)": (
        ["Increasing dietary fibre and fluids to avoid straining.", "Topical treatment; procedures if persistent."],
        ["topical_skin"],
        ["Should the bleeding be investigated further?"],
    ),
    "Heart attack": (
        ["Emergency treatment — this is time critical.", "Long-term risk reduction afterwards."],
        [],
        ["What can I do to reduce the risk of another?", "What cardiac rehabilitation is available?"],
    ),
    "Varicose veins": (
        ["Compression and leg elevation.", "Procedures where symptoms are significant."],
        [],
        ["Am I a candidate for a procedure?"],
    ),
    "Hypothyroidism": (
        ["Blood tests to confirm and to guide treatment.", "Hormone replacement, adjusted by results."],
        ["thyroid_medicine"],
        ["How often will my levels be checked?"],
    ),
    "Hyperthyroidism": (
        ["Blood tests and often imaging.", "Several treatment routes exist; the choice is a discussion with a specialist."],
        ["thyroid_medicine"],
        ["What are the treatment options and their trade-offs?"],
    ),
    "Hypoglycemia": (
        ["Treating the immediate episode.", "Finding why it happened, especially if you take diabetes medicines."],
        ["antidiabetic"],
        ["Why am I having these episodes?", "Should my diabetes medicines be reviewed?"],
    ),
    "Osteoarthristis": (
        ["Activity, weight management and physiotherapy.", "Pain management; joint procedures where severe."],
        ["analgesic"],
        ["Would physiotherapy help?", "Which pain relief suits my other conditions?"],
    ),
    "Arthritis": (
        ["Identifying the type, which changes treatment entirely.", "Anti-inflammatory and disease-modifying treatment where appropriate."],
        ["analgesic", "corticosteroid"],
        ["Which type of arthritis is this?", "Should I see a rheumatologist?"],
    ),
    "(vertigo) Paroymsal  Positional Vertigo": (
        ["Assessment to confirm the type of vertigo.", "Repositioning manoeuvres, performed or taught by a clinician."],
        [],
        ["Can you show me the repositioning manoeuvre?", "Is driving safe at the moment?"],
    ),
    "Acne": (
        ["A consistent skin routine.", "Topical treatment, with oral options for more severe cases."],
        ["topical_skin", "antibiotic"],
        ["How long before I should expect improvement?"],
    ),
    "Urinary tract infection": (
        ["Fluids and symptom relief.", "Antibiotics where the infection is confirmed or strongly suspected."],
        ["antibiotic", "analgesic"],
        ["Should a urine sample be sent?", "What if this keeps recurring?"],
    ),
    "Psoriasis": (
        ["Emollients and topical treatment.", "Light therapy or systemic treatment for more extensive disease."],
        ["topical_skin", "corticosteroid"],
        ["Should I be referred to dermatology?", "Could this be affecting my joints?"],
    ),
    "Impetigo": (
        ["Hygiene measures to limit spread.", "Topical or oral antibiotics."],
        ["antibiotic", "topical_skin"],
        ["How long should I stay off work or school?"],
    ),
}


def build() -> dict:
    descriptions: dict[str, str] = {}
    path = RAW_DIR / "symptom_Description.csv"
    if path.exists():
        for row in csv.DictReader(path.open(encoding="latin-1")):
            descriptions[" ".join(row["Disease"].split())] = row["Description"].strip()

    conditions: dict[str, dict] = {}
    for condition, (approaches, classes, questions) in CURATED.items():
        key = " ".join(condition.split())
        conditions[key] = {
            "summary": descriptions.get(key, ""),
            "summary_source": DESCRIPTION_SOURCE if key in descriptions else None,
            "summary_source_url": DESCRIPTION_URL if key in descriptions else None,
            "approaches": approaches,
            "medication_classes": classes,
            "questions": [*questions, *UNIVERSAL_QUESTIONS],
        }
    return {
        "_readme": [
            "Generated by ml/knowledge/build_condition_knowledge.py — do not edit by hand.",
            "",
            "Summaries come from the Disease Symptom Description Dataset (CC BY-SA 4.0).",
            "Approaches, medication classes and questions are curated for this project.",
            "",
            "The dataset's symptom_precaution.csv is deliberately NOT used: it contains",
            "'stop taking drug', 'take radioactive iodine treatment', 'take otc pain",
            "reliver', unevidenced folk remedies, and 'salt baths' for hypertension.",
            "",
            "Nothing here states a dose or tells anyone to start, stop or change a",
            "medicine. Tests enforce that.",
            "",
            "NOT REVIEWED BY A CLINICIAN.",
        ],
        "conditions": conditions,
    }


def main() -> int:
    payload = build()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    with_summary = sum(1 for c in payload["conditions"].values() if c["summary"])
    print(f"Wrote {OUTPUT}")
    print(f"  conditions: {len(payload['conditions'])}, with a sourced summary: {with_summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
