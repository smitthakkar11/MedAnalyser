import { FeatureIcon, type FeatureIconName } from '@/components/FeatureIcon';
import { HeroVisual } from '@/components/HeroVisual';
import { MedicalDisclaimer } from '@/components/MedicalDisclaimer';
import { SystemStatus } from '@/components/SystemStatus';

interface Step {
  title: string;
  body: string;
  icon: FeatureIconName;
  /** Tailwind gradient stops for this step's accent. */
  accent: string;
  glow: string;
}

const STEPS: readonly Step[] = [
  {
    icon: 'stethoscope',
    title: 'Describe it, or upload it',
    body: 'Type how you feel in plain language, attach a lab report, or both. MedAnalyser reads the PDF and pulls out the values that matter — including the scanned ones.',
    accent: 'from-accent-teal to-accent-lime',
    glow: 'group-hover:shadow-accent-teal/30',
  },
  {
    icon: 'chat',
    title: 'Answer what actually matters',
    body: 'No fixed questionnaire. Follow-up questions adapt to what you have already said — past consultations, what you were prescribed, whether it helped.',
    accent: 'from-accent-blue to-accent-violet',
    glow: 'group-hover:shadow-accent-blue/30',
  },
  {
    icon: 'evidence',
    title: 'See the reasoning, not just the answer',
    body: 'Every suggestion is retrieved from a curated medical knowledge base and cited, with the gaps in your information listed rather than quietly filled in.',
    accent: 'from-accent-violet to-accent-magenta',
    glow: 'group-hover:shadow-accent-violet/30',
  },
  {
    icon: 'shield',
    title: 'Get pointed at the right door',
    body: 'A recommended specialty, the questions worth asking, and clinicians near you — so the appointment you book is the one you needed.',
    accent: 'from-accent-amber to-accent-magenta',
    glow: 'group-hover:shadow-accent-amber/30',
  },
] as const;

const STATS = [
  {
    value: '4',
    label: 'inputs combined',
    detail: 'Symptoms, reports, history, medications',
    accent: 'from-accent-teal to-accent-lime',
  },
  {
    value: '0',
    label: 'invented findings',
    detail: 'Answers are grounded in retrieved sources',
    accent: 'from-accent-blue to-accent-violet',
  },
  {
    value: '1',
    label: 'safety layer that overrides',
    detail: 'Deterministic, independent of the model',
    accent: 'from-accent-amber to-accent-magenta',
  },
] as const;

export function LandingPage() {
  return (
    <div>
      {/* ---------------------------------------------------------------- Hero */}
      <section className="relative isolate overflow-hidden border-b border-ink-200 dark:border-ink-800">
        {/* Ambient colour field */}
        <div aria-hidden="true" className="pointer-events-none absolute inset-0 -z-10">
          <div className="animate-drift absolute -left-32 -top-32 size-[38rem] rounded-full bg-accent-violet/12 blur-3xl dark:bg-accent-violet/18" />
          <div className="animate-float-slow absolute -right-40 top-10 size-[34rem] rounded-full bg-accent-teal/12 blur-3xl dark:bg-accent-teal/16" />
        </div>

        <div className="mx-auto grid max-w-[1400px] items-center gap-16 px-6 pb-20 pt-20 sm:pb-28 sm:pt-24 lg:grid-cols-[1.05fr_1fr] lg:gap-12 lg:px-10">
          <div>
            <span className="inline-flex items-center gap-2 rounded-full border border-ink-200 bg-ink-0/60 px-3.5 py-1.5 text-xs font-semibold backdrop-blur dark:border-ink-800 dark:bg-ink-900/60">
              <span className="size-1.5 rounded-full bg-gradient-to-r from-accent-teal to-accent-lime" />
              <span className="bg-gradient-to-r from-accent-teal via-accent-blue to-accent-violet bg-clip-text text-transparent">
                Reports, symptoms and history — read together
              </span>
            </span>

            <h1 className="mt-7 max-w-[16ch] text-display">
              Know what
              <br />
              you&rsquo;re walking
              <br />
              <span className="bg-gradient-to-r from-accent-teal via-accent-blue to-accent-violet bg-clip-text text-transparent">
                in with.
              </span>
            </h1>

            <p className="mt-8 max-w-xl text-lg leading-snug font-medium text-ink-700 sm:text-xl dark:text-ink-300">
              Upload a report you can&rsquo;t read. Describe a pain you can&rsquo;t name.
              MedAnalyser connects your symptoms, lab values and medical history into one clear
              picture — and tells you which specialist is worth your time.
            </p>

            <div className="mt-10 flex flex-wrap items-center gap-3">
              <button
                type="button"
                className="group inline-flex items-center gap-2 rounded-full bg-gradient-to-r from-accent-blue to-accent-violet px-7 py-4 text-base font-semibold text-white shadow-lg shadow-accent-violet/25 transition hover:shadow-xl hover:shadow-accent-violet/40"
              >
                Start an assessment
                <span
                  aria-hidden="true"
                  className="transition-transform group-hover:translate-x-1"
                >
                  →
                </span>
              </button>
              <a
                href="#how-it-works"
                className="inline-flex items-center rounded-full border border-ink-300 px-7 py-4 text-base font-semibold transition hover:border-ink-950 dark:border-ink-700 dark:hover:border-ink-0"
              >
                How it works
              </a>
            </div>
          </div>

          <HeroVisual />
        </div>
      </section>

      {/* ------------------------------------------------------- Stats (dark) */}
      <section className="relative isolate overflow-hidden bg-ink-950 text-ink-0">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 -z-10 opacity-70"
        >
          <div className="animate-drift absolute -left-20 top-0 size-96 rounded-full bg-accent-violet/25 blur-3xl" />
          <div className="animate-float-slow absolute right-0 -bottom-24 size-96 rounded-full bg-accent-teal/20 blur-3xl" />
        </div>

        <dl className="mx-auto grid max-w-[1400px] gap-12 px-6 py-20 sm:grid-cols-3 sm:gap-8 sm:py-24 lg:px-10">
          {STATS.map((stat) => (
            <div key={stat.label}>
              <dt className="sr-only">{stat.label}</dt>
              <dd>
                <span
                  className={`block bg-gradient-to-br ${stat.accent} bg-clip-text text-7xl font-extrabold tracking-tighter text-transparent sm:text-8xl`}
                >
                  {stat.value}
                </span>
                <span className="mt-4 block text-lg font-semibold">{stat.label}</span>
                <span className="mt-1 block text-sm text-ink-400">{stat.detail}</span>
              </dd>
            </div>
          ))}
        </dl>
      </section>

      {/* --------------------------------------------------------- How it works */}
      <section
        id="how-it-works"
        aria-labelledby="how-it-works-heading"
        className="scroll-mt-20 border-b border-ink-200 dark:border-ink-800"
      >
        <div className="mx-auto max-w-[1400px] px-6 py-20 sm:py-28 lg:px-10">
          <h2 id="how-it-works-heading" className="max-w-[14ch] text-headline">
            Built like a clinic,
            <br />
            <span className="bg-gradient-to-r from-accent-magenta to-accent-amber bg-clip-text text-transparent">
              not a chatbot.
            </span>
          </h2>

          <ol className="mt-14 border-t border-ink-950 dark:border-ink-0">
            {STEPS.map((step, index) => (
              <li
                key={step.title}
                className="group relative border-b border-ink-200 transition-colors hover:bg-ink-50 dark:border-ink-800 dark:hover:bg-ink-900"
              >
                {/* Accent rail, revealed on hover */}
                <span
                  aria-hidden="true"
                  className={`absolute inset-y-0 left-0 w-0.5 origin-top scale-y-0 bg-gradient-to-b ${step.accent} transition-transform duration-300 group-hover:scale-y-100`}
                />

                <div className="grid items-start gap-5 py-8 pl-4 sm:grid-cols-[auto_1fr_auto] sm:gap-10 sm:py-10">
                  <span
                    className={`bg-gradient-to-br font-mono text-sm font-semibold sm:pt-3 ${step.accent} bg-clip-text text-transparent`}
                  >
                    {String(index + 1).padStart(2, '0')}
                  </span>

                  <div className="grid gap-3 sm:grid-cols-[1fr_1.2fr] sm:gap-10">
                    <h3 className="text-2xl font-bold tracking-tight sm:text-3xl">
                      {step.title}
                    </h3>
                    <p className="text-base leading-relaxed text-ink-600 dark:text-ink-400">
                      {step.body}
                    </p>
                  </div>

                  <span
                    className={`hidden shrink-0 rounded-xl bg-gradient-to-br p-3 text-white shadow-md transition-all duration-300 sm:block ${step.accent} ${step.glow} group-hover:-translate-y-0.5 group-hover:shadow-lg`}
                  >
                    <FeatureIcon name={step.icon} className="size-6" />
                  </span>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* ------------------------------------------------------------- Safety */}
      <section
        id="safety"
        aria-labelledby="safety-heading"
        className="scroll-mt-20 border-b border-ink-200 dark:border-ink-800"
      >
        <div className="mx-auto max-w-[1400px] px-6 py-20 sm:py-28 lg:px-10">
          <div className="grid gap-12 lg:grid-cols-[1fr_1.2fr] lg:gap-20">
            <div>
              <h2 id="safety-heading" className="max-w-[12ch] text-headline">
                The safety layer
                <span className="bg-gradient-to-r from-danger-500 to-accent-amber bg-clip-text text-transparent">
                  {' '}
                  outranks the AI.
                </span>
              </h2>
            </div>

            <div className="space-y-8">
              <p className="text-lg leading-relaxed text-ink-700 dark:text-ink-300">
                Red-flag detection is not a prompt. It is a deterministic rule layer that runs
                independently of the model and can override its output entirely. A language
                model can be talked out of an emergency finding — a rule table cannot.
              </p>
              <p className="text-lg leading-relaxed text-ink-700 dark:text-ink-300">
                When something looks urgent, that warning takes priority over every other part
                of the result. MedAnalyser will not reassure you to keep the conversation
                pleasant.
              </p>
              <MedicalDisclaimer />
            </div>
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------ System status */}
      <div className="mx-auto max-w-[1400px] px-6 py-20 sm:py-24 lg:px-10">
        <SystemStatus />
      </div>
    </div>
  );
}
