import {
  ArrowRight,
  ArrowUpRight,
  Check,
  FileCode2,
  GitPullRequest,
  ScanSearch,
  ShieldCheck,
  Terminal,
} from "lucide-react";
import { GithubBrandIcon as Github } from "@/components/GithubBrandIcon";
import { BrandMark } from "@/components/BrandMark";
import { useCases } from "@/app/use-cases/useCases";

const repositoryUrl = "https://github.com/eyeinthesky6/indexpilot";
const publicSiteUrl = "https://eyeinthesky6.github.io/indexpilot";
const releaseUrl = `${repositoryUrl}/releases/tag/v1.1.0a6`;
const installationUrl = `${repositoryUrl}/blob/main/docs/INSTALLATION.md`;
const usageUrl = `${repositoryUrl}/blob/main/docs/USAGE.md`;
const buildStoryUrl = `${repositoryUrl}/blob/main/docs/articles/01_DATABASE_DNA.md`;
const evidenceLimitsUrl = `${repositoryUrl}/blob/main/docs/ROADMAP.md`;
const teamPreviewUrl = `${repositoryUrl}/issues/new?template=team_workflow.yml`;
const teamPreviewPlanUrl = `${repositoryUrl}/blob/main/docs/TEAM_PREVIEW.md`;
const teamPreviewRollupUrl = `${repositoryUrl}/actions/workflows/team-preview-rollup.yml`;
const firstValueUrl = `${repositoryUrl}/discussions/categories/show-and-tell`;
const demoUrl = "https://app.arcade.software/share/ENmH1Og01OjwfF31JvGR";
const demoEmbedUrl = "https://demo.arcade.software/ENmH1Og01OjwfF31JvGR?embed";

const activitySignals = [
  {
    label: "PyPI downloads per month",
    image: "https://static.pepy.tech/badge/indexpilot/month",
    source: "https://pepy.tech/projects/indexpilot",
  },
  {
    label: "GitHub stars",
    image: "https://img.shields.io/github/stars/eyeinthesky6/indexpilot?logo=github&label=stars",
    source: repositoryUrl,
  },
  {
    label: "GitHub forks",
    image: "https://img.shields.io/github/forks/eyeinthesky6/indexpilot?logo=github&label=forks",
    source: `${repositoryUrl}/forks`,
  },
  {
    label: "Team response rollup status",
    image: `${repositoryUrl}/actions/workflows/team-preview-rollup.yml/badge.svg`,
    source: teamPreviewRollupUrl,
  },
];

const verdicts = [
  {
    name: "worth_benchmarking",
    tone: "bg-[#b8f34a] text-[#0b1728]",
    summary: "The exact hypothetical shape was selected and cleared the advisory planner threshold.",
    next: "Benchmark latency, writes, size, build time, and rollback on a production copy.",
  },
  {
    name: "existing_overlap",
    tone: "bg-[#d9e7f5] text-[#0b1728]",
    summary: "A comparable existing B-tree already covers the proposal's leading prefix.",
    next: "Inspect both shapes. This is review evidence, never automatic drop advice.",
  },
  {
    name: "not_supported_by_current_planner_evidence",
    tone: "bg-[#f3d5a8] text-[#0b1728]",
    summary: "The planner did not select the exact shape or its improvement stayed below threshold.",
    next: "Inspect the plan or test another shape. Do not infer that the index is harmful.",
  },
  {
    name: "inconclusive",
    tone: "bg-[#e8e5de] text-[#0b1728]",
    summary: "Workload, permissions, or planner evidence was missing or insufficient.",
    next: "Collect representative traffic or repair evidence access before deciding.",
  },
];

const structuredData = {
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  name: "IndexPilot",
  applicationCategory: "DeveloperApplication",
  operatingSystem: "Windows, macOS, Linux",
  description:
    "Stop bad PostgreSQL indexes before production by checking proposed indexes against your real workload.",
  codeRepository: repositoryUrl,
  license: "https://opensource.org/license/mit",
  softwareVersion: "1.1.0a6",
  offers: { "@type": "Offer", price: "0", priceCurrency: "USD" },
};

export default function PublicHome() {
  return (
    <div className="min-h-screen overflow-x-hidden bg-[#f7f5ee] text-[#0b1728]">
      <a
        href="#content"
        className="sr-only z-[100] rounded bg-[#b8f34a] px-4 py-2 font-semibold text-[#0b1728] focus:not-sr-only focus:fixed focus:left-4 focus:top-4"
      >
        Skip to content
      </a>

      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(structuredData) }}
      />

      <div className="border-b border-[#0b1728]/10 bg-[#b8f34a] px-4 py-2 text-center font-mono text-[11px] font-semibold uppercase tracking-[0.16em] text-[#0b1728] sm:text-xs">
        PostgreSQL index review · advisory by design · never applies physical DDL
      </div>

      <header className="sticky top-0 z-50 border-b border-[#0b1728]/10 bg-[#f7f5ee]/90 backdrop-blur-xl">
        <div className="mx-auto flex min-h-[4.5rem] max-w-7xl items-center justify-between px-5 py-3 sm:px-8 lg:px-10">
          <a href="#top" className="group flex items-center gap-3" aria-label="IndexPilot home">
            <BrandMark className="h-10 w-10 transition-transform duration-300 group-hover:-rotate-3" />
            <span className="font-display text-xl font-bold tracking-[-0.04em]">IndexPilot</span>
          </a>

          <nav className="hidden items-center gap-7 text-sm font-semibold md:flex" aria-label="Main navigation">
            <a href="#why" className="transition-colors hover:text-[#456b00]">
              Why it exists
            </a>
            <a href="#how" className="transition-colors hover:text-[#456b00]">
              Evidence path
            </a>
            <a href="#verdicts" className="transition-colors hover:text-[#456b00]">
              Verdicts
            </a>
            <a href="#team-preview" className="transition-colors hover:text-[#456b00]">
              Team preview
            </a>
            <a href={usageUrl} className="transition-colors hover:text-[#456b00]">
              Docs
            </a>
          </nav>

          <a
            href={repositoryUrl}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2 rounded-full border border-[#0b1728] px-4 py-2 text-sm font-bold transition-colors hover:bg-[#0b1728] hover:text-[#f7f5ee]"
          >
            <Github className="h-4 w-4" />
            <span className="hidden sm:inline">GitHub</span>
          </a>
        </div>
      </header>

      <main id="content">
        <section id="top" className="relative isolate overflow-hidden bg-[#0b1728] text-[#f7f5ee]">
          <div className="site-grid pointer-events-none absolute inset-0 opacity-20" />
          <div className="hero-glow pointer-events-none absolute inset-0" />
          <div className="relative mx-auto max-w-7xl px-5 pt-6 sm:px-8 sm:pt-8 lg:px-10">
            <div aria-label="Live project activity">
              <p className="font-mono text-[11px] font-bold uppercase tracking-[0.18em] text-[#8fa0b4]">
                Live project activity
              </p>
              <div className="mt-2 flex flex-wrap gap-2">
                {activitySignals.map((signal) => (
                  <a
                    key={signal.label}
                    href={signal.source}
                    aria-label={`${signal.label}: open source`}
                    className="inline-flex items-center rounded-lg border border-white/15 bg-white/[0.07] px-1.5 py-1 leading-none shadow-sm transition hover:border-[#b8f34a]/55 hover:bg-white/[0.11] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#b8f34a]"
                  >
                    {/* Live SVG badges are intentionally external so their source values update. */}
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={signal.image}
                      alt={signal.label}
                      className="h-[22px] w-auto sm:h-6"
                      loading="eager"
                    />
                  </a>
                ))}
              </div>
            </div>
          </div>

          <div className="relative mx-auto grid max-w-7xl gap-14 px-5 pb-20 pt-12 sm:px-8 sm:pb-28 sm:pt-14 lg:grid-cols-[1.08fr_0.92fr] lg:items-center lg:px-10 lg:pb-32 lg:pt-16">
            <div>
              <div className="mb-7 inline-flex items-center gap-2 rounded-full border border-[#b8f34a]/35 bg-[#b8f34a]/10 px-3 py-1.5 font-mono text-xs uppercase tracking-[0.14em] text-[#b8f34a]">
                <GitPullRequest className="h-3.5 w-3.5" />
                PostgreSQL index review for migration PRs
              </div>

              <h1 className="max-w-4xl font-display text-5xl font-bold leading-[0.94] tracking-[-0.055em] sm:text-6xl lg:text-[5rem]">
                Stop bad PostgreSQL indexes{" "}
                <span className="text-[#b8f34a]">before production.</span>
              </h1>

              <p className="mt-7 max-w-2xl text-lg leading-8 text-[#cbd4df] sm:text-xl">
                IndexPilot checks the exact <code className="text-[#f7f5ee]">CREATE INDEX</code> in
                your migration against observed workload, comparable indexes, and optional
                hypothetical plans. It then leaves a review artifact your team can inspect.
              </p>

              <div className="mt-9 flex flex-col gap-3 sm:flex-row">
                <a
                  href="#quickstart"
                  className="inline-flex items-center justify-center gap-2 rounded-full bg-[#b8f34a] px-6 py-3.5 text-sm font-bold text-[#0b1728] transition-transform hover:-translate-y-0.5"
                >
                  Catch an overlap in 60 seconds
                  <ArrowRight className="h-4 w-4" />
                </a>
                <a
                  href={demoUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center justify-center gap-2 rounded-full border border-[#f7f5ee]/25 px-6 py-3.5 text-sm font-bold transition-colors hover:border-[#f7f5ee]/60 hover:bg-white/5"
                >
                  Watch the actual review
                  <ArrowUpRight className="h-4 w-4" />
                </a>
              </div>

              <ul className="mt-9 flex flex-wrap gap-x-6 gap-y-3 text-sm text-[#aeb9c7]" aria-label="Project facts">
                {[
                  "Read-only evidence path",
                  "JSON · Markdown · SARIF",
                  "MIT licensed",
                ].map((fact) => (
                  <li key={fact} className="flex items-center gap-2">
                    <Check className="h-4 w-4 text-[#b8f34a]" />
                    {fact}
                  </li>
                ))}
              </ul>
            </div>

            <div className="relative lg:pl-6">
              <div className="absolute -inset-6 -z-10 rotate-2 rounded-[2rem] border border-[#b8f34a]/20 bg-[#b8f34a]/5" />
              <div className="overflow-hidden rounded-2xl border border-white/15 bg-[#07101d] shadow-2xl shadow-black/40">
                <div className="flex items-center justify-between border-b border-white/10 px-5 py-3">
                  <div className="flex gap-1.5" aria-hidden="true">
                    <span className="h-2.5 w-2.5 rounded-full bg-[#ef6a6a]" />
                    <span className="h-2.5 w-2.5 rounded-full bg-[#efc56a]" />
                    <span className="h-2.5 w-2.5 rounded-full bg-[#b8f34a]" />
                  </div>
                  <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-[#738196]">
                    illustrative review receipt
                  </span>
                </div>
                <div className="receipt-scan relative space-y-5 p-5 font-mono text-[12px] leading-6 sm:p-7 sm:text-[13px]">
                  <div className="text-[#7f91a6]">
                    <span className="text-[#b8f34a]">$</span> indexpilot review \<br />
                    <span className="pl-4">--migration-file migrations/add_orders_index.sql \</span>
                    <br />
                    <span className="pl-4">--hypopg --sarif-output artifacts/indexpilot.sarif</span>
                  </div>

                  <div className="rounded-xl border border-white/10 bg-white/[0.035] p-4">
                    <p className="mb-3 text-[10px] uppercase tracking-[0.18em] text-[#738196]">
                      proposal 01
                    </p>
                    <p className="break-words text-[#dce3eb]">
                      public.orders (tenant_id, created_at)
                    </p>
                    <div className="my-4 h-px bg-white/10" />
                    <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2">
                      <dt className="text-[#738196]">workload</dt>
                      <dd className="text-right text-[#dce3eb]">observed</dd>
                      <dt className="text-[#738196]">overlap</dt>
                      <dd className="text-right text-[#dce3eb]">none found</dd>
                      <dt className="text-[#738196]">hypopg</dt>
                      <dd className="text-right text-[#dce3eb]">selected</dd>
                    </dl>
                  </div>

                  <div className="flex items-center justify-between gap-4 rounded-xl bg-[#b8f34a] px-4 py-3 text-[#0b1728]">
                    <span className="text-[10px] font-bold uppercase tracking-[0.18em]">Verdict</span>
                    <span className="font-bold">worth_benchmarking</span>
                  </div>
                  <p className="text-[11px] text-[#738196]">
                    Advisory only. Planner cost is not production latency.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="border-b border-[#0b1728]/10 bg-[#f7f5ee]">
          <div className="mx-auto max-w-7xl px-5 py-20 sm:px-8 sm:py-24 lg:px-10">
            <p className="font-mono text-xs font-semibold uppercase tracking-[0.2em] text-[#527408]">Start with your problem</p>
            <h2 className="mt-4 max-w-3xl font-display text-4xl font-bold tracking-[-0.045em] sm:text-5xl">What are you trying to decide?</h2>
            <div className="mt-10 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {useCases.map((item) => (
                <a key={item.slug} href={`${publicSiteUrl}/use-cases/${item.slug}/`} className="group rounded-2xl border border-[#0b1728]/15 bg-white p-6 transition-transform hover:-translate-y-1">
                  <h3 className="font-display text-xl font-bold">{item.title}</h3>
                  <p className="mt-3 text-sm leading-6 text-[#536070]">{item.description}</p>
                  <span className="mt-5 inline-flex items-center gap-2 text-sm font-bold text-[#456b00]">See the decision path <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" /></span>
                </a>
              ))}
            </div>
          </div>
        </section>

        <section id="why" className="border-b border-[#0b1728]/10">
          <div className="mx-auto max-w-7xl px-5 py-20 sm:px-8 sm:py-28 lg:px-10">
            <div className="grid gap-10 lg:grid-cols-[0.8fr_1.2fr] lg:items-end">
              <div>
                <p className="font-mono text-xs font-semibold uppercase tracking-[0.2em] text-[#527408]">
                  The missing decision layer
                </p>
                <h2 className="mt-4 font-display text-4xl font-bold leading-tight tracking-[-0.045em] sm:text-5xl">
                  An index is cheap to propose. It is expensive to keep.
                </h2>
              </div>
              <p className="max-w-2xl text-lg leading-8 text-[#536070] lg:justify-self-end">
                Every accepted index adds write work, storage, cache pressure, backup weight, and
                maintenance. Migration linters check whether DDL is safe to run. Advisers suggest
                possible indexes. IndexPilot asks the in-between question: does this exact proposal
                have enough evidence to deserve a real benchmark?
              </p>
            </div>

            <div className="mt-14 grid overflow-hidden rounded-3xl border border-[#0b1728]/15 bg-white md:grid-cols-3">
              {[
                {
                  step: "01 / Proposal",
                  icon: FileCode2,
                  title: "Review the migration",
                  body: "Parse the supplied PostgreSQL CREATE INDEX locally. Unsupported shapes fail clearly instead of being approximated.",
                },
                {
                  step: "02 / Evidence",
                  icon: ScanSearch,
                  title: "Interrogate reality",
                  body: "Read pg_stat_statements, catalog overlap, and optional session-local HypoPG plans in a read-only transaction.",
                },
                {
                  step: "03 / Record",
                  icon: Terminal,
                  title: "Leave a decision trail",
                  body: "Write stable JSON, human-readable Markdown, and SARIF that can meet a reviewer in the pull request.",
                },
              ].map(({ step, icon: Icon, title, body }, index) => (
                <article
                  key={step}
                  className={`p-7 sm:p-9 ${index < 2 ? "border-b border-[#0b1728]/10 md:border-b-0 md:border-r" : ""}`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-[11px] font-bold uppercase tracking-[0.18em] text-[#6b7582]">
                      {step}
                    </span>
                    <Icon className="h-5 w-5 text-[#527408]" />
                  </div>
                  <h3 className="mt-9 font-display text-2xl font-bold tracking-[-0.035em]">{title}</h3>
                  <p className="mt-3 leading-7 text-[#5a6572]">{body}</p>
                </article>
              ))}
            </div>

            <div className="mt-10 grid overflow-hidden rounded-3xl bg-[#0b1728] text-[#f7f5ee] lg:grid-cols-[0.82fr_1.18fr]">
              <div className="border-b border-white/10 p-7 sm:p-9 lg:border-b-0 lg:border-r">
                <p className="font-mono text-xs font-semibold uppercase tracking-[0.2em] text-[#b8f34a]">
                  The origin
                </p>
                <h3 className="mt-4 font-display text-3xl font-bold leading-tight tracking-[-0.04em] sm:text-4xl">
                  It started with DNA storage. A live database changed the question.
                </h3>
              </div>
              <div className="p-7 sm:p-9">
                <p className="text-lg leading-8 text-[#cbd4df]">
                  DNA&apos;s information density inspired the first database-genome experiment. But
                  synthesis and sequencing suit archival storage, not the millisecond path of an
                  algorithmic-trading system. That system exposed a more immediate problem: a
                  plausible index can still be the wrong tradeoff.
                </p>
                <p className="mt-5 leading-7 text-[#aeb9c7]">
                  IndexPilot became the useful part of that experiment: a narrow, read-only review
                  step for the exact index a team is considering. It does not store data in DNA.
                </p>
                <div className="mt-7 flex flex-wrap gap-x-6 gap-y-3 text-sm font-bold">
                  <a href={buildStoryUrl} className="inline-flex items-center gap-2 text-[#b8f34a]">
                    Read the build story <ArrowUpRight className="h-4 w-4" />
                  </a>
                  <a href={evidenceLimitsUrl} className="inline-flex items-center gap-2 text-[#b8f34a]">
                    Read the evidence limits <ArrowUpRight className="h-4 w-4" />
                  </a>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section id="how" className="bg-white">
          <div className="mx-auto max-w-7xl px-5 py-20 sm:px-8 sm:py-28 lg:px-10">
            <div className="max-w-3xl">
              <p className="font-mono text-xs font-semibold uppercase tracking-[0.2em] text-[#527408]">
                Evidence in. A cautious next step out.
              </p>
              <h2 className="mt-4 font-display text-4xl font-bold tracking-[-0.045em] sm:text-5xl">
                No autopilot. No mystery score.
              </h2>
            </div>

            <div className="mt-14 grid gap-5 lg:grid-cols-[1fr_auto_1fr_auto_1fr] lg:items-stretch">
              {[
                {
                  kicker: "Observed workload",
                  title: "What your database actually runs",
                  body: "Aggregated pg_stat_statements become query fingerprints. Raw workload SQL is not written to the report.",
                },
                {
                  kicker: "Catalog + HypoPG",
                  title: "What exists and what might change",
                  body: "Compare valid B-trees, then optionally ask whether PostgreSQL selects the exact hypothetical shape with EXPLAIN instead of ANALYZE.",
                },
                {
                  kicker: "Portable evidence",
                  title: "What a human should do next",
                  body: "Receive one bounded verdict, its limitations, and a practical next step. Positive means benchmark it, never ship it blindly.",
                },
              ].map((item, index) => (
                <div key={item.kicker} className="contents">
                  <article className="rounded-3xl border border-[#0b1728]/10 bg-[#f7f5ee] p-7 sm:p-9">
                    <span className="font-mono text-[11px] font-bold uppercase tracking-[0.18em] text-[#527408]">
                      {item.kicker}
                    </span>
                    <h3 className="mt-5 font-display text-2xl font-bold tracking-[-0.035em]">
                      {item.title}
                    </h3>
                    <p className="mt-3 leading-7 text-[#5a6572]">{item.body}</p>
                  </article>
                  {index < 2 ? (
                    <ArrowRight className="mx-auto hidden h-5 w-5 self-center text-[#87a348] lg:block" />
                  ) : null}
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="quickstart" className="bg-[#dfe9cc]">
          <div className="mx-auto grid max-w-7xl gap-12 px-5 py-20 sm:px-8 sm:py-24 lg:grid-cols-[0.82fr_1.18fr] lg:items-center lg:px-10">
            <div>
              <p className="font-mono text-xs font-semibold uppercase tracking-[0.2em] text-[#456100]">
                Quick start · Early alpha
              </p>
              <h2 className="mt-4 font-display text-4xl font-bold tracking-[-0.045em] sm:text-5xl">
                Catch an overlapping index in 60 seconds.
              </h2>
              <p className="mt-5 max-w-xl text-lg leading-8 text-[#435043]">
                Run the sanitized example with no PostgreSQL service or database secret. It should
                flag an existing overlap and write a review artifact you can inspect.
              </p>
              <div className="mt-7 flex flex-wrap gap-3">
                <a
                  href={installationUrl}
                  className="inline-flex items-center gap-2 font-bold underline decoration-2 underline-offset-4"
                >
                  Installation guide <ArrowUpRight className="h-4 w-4" />
                </a>
                <a
                  href={releaseUrl}
                  className="inline-flex items-center gap-2 font-bold underline decoration-2 underline-offset-4"
                >
                  Release notes <ArrowUpRight className="h-4 w-4" />
                </a>
                <a
                  href={demoUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-2 font-bold underline decoration-2 underline-offset-4"
                >
                  Watch the actual review <ArrowUpRight className="h-4 w-4" />
                </a>
                <a
                  href={firstValueUrl}
                  className="inline-flex items-center gap-2 font-bold underline decoration-2 underline-offset-4"
                >
                  Share a sanitized result <ArrowUpRight className="h-4 w-4" />
                </a>
              </div>
              <p className="mt-7 border-l-2 border-[#456100] pl-4 text-sm leading-6 text-[#435043]">
                Early alpha supports plain-column, non-unique, ascending B-trees. This example proves
                the review path, not production performance. When ready, continue with the{" "}
                <a href={usageUrl} className="font-bold underline decoration-2 underline-offset-4">
                  live read-only PostgreSQL workflow
                </a>
                .
              </p>
            </div>

            <div className="overflow-hidden rounded-2xl border border-[#0b1728]/20 bg-[#0b1728] text-[#dce3eb] shadow-xl shadow-[#456100]/10">
              <div className="flex items-center justify-between border-b border-white/10 px-5 py-3 font-mono text-[10px] uppercase tracking-[0.18em] text-[#8090a3]">
                <span>shell</span>
                <span>Python 3.10+</span>
              </div>
              <pre className="overflow-x-auto p-5 font-mono text-[12px] leading-7 sm:p-7 sm:text-[13px]">
                <code>
                  <span className="text-[#b8f34a]">$</span>{" "}git clone --depth 1 {repositoryUrl}.git{"\n"}
                  <span className="text-[#b8f34a]">$</span>{" "}cd indexpilot{"\n\n"}
                  <span className="text-[#b8f34a]">$</span>{" "}uvx --from &quot;indexpilot==1.1.0a6&quot; indexpilot review \{"\n"}
                  {"  "}--migration-file examples/quickstart/migration.sql \{"\n"}
                  {"  "}--snapshot-file examples/quickstart/workload-snapshot.json \{"\n"}
                  {"  "}--output artifacts/first-review.json \{"\n"}
                  {"  "}--markdown-output artifacts/first-review.md \{"\n"}
                  {"  "}--stdout
                </code>
              </pre>
            </div>
          </div>

          <div className="mx-auto max-w-7xl px-5 pb-20 sm:px-8 sm:pb-24 lg:px-10">
            <div className="overflow-hidden rounded-3xl border border-[#0b1728]/20 bg-[#0b1728] shadow-2xl shadow-[#456100]/15">
              <div className="flex flex-col gap-3 border-b border-white/10 px-5 py-5 text-[#f7f5ee] sm:flex-row sm:items-center sm:justify-between sm:px-7">
                <div>
                  <p className="font-mono text-[11px] font-bold uppercase tracking-[0.18em] text-[#b8f34a]">
                    Actual-use walkthrough
                  </p>
                  <h3 className="mt-1 font-display text-2xl font-bold tracking-[-0.035em]">
                    See the migration, command, overlap verdict, and saved evidence.
                  </h3>
                </div>
                <a
                  href={demoUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex shrink-0 items-center gap-2 text-sm font-bold text-[#b8f34a]"
                >
                  Open in a new tab <ArrowUpRight className="h-4 w-4" />
                </a>
              </div>
              <div className="aspect-[1270/760] w-full bg-[#07101d]">
                <iframe
                  src={demoEmbedUrl}
                  title="IndexPilot actual database-free index review"
                  className="h-full w-full border-0"
                  loading="lazy"
                  allowFullScreen
                />
              </div>
            </div>
            <p className="mt-4 text-sm leading-6 text-[#435043]">
              This walkthrough uses the bundled sanitized quickstart and never connects to a
              PostgreSQL database. It shows the same <code>existing_overlap</code> result you can
              reproduce locally.
            </p>
          </div>
        </section>

        <section id="verdicts" className="border-b border-[#0b1728]/10 bg-[#f7f5ee]">
          <div className="mx-auto max-w-7xl px-5 py-20 sm:px-8 sm:py-28 lg:px-10">
            <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
              <div className="max-w-3xl">
                <p className="font-mono text-xs font-semibold uppercase tracking-[0.2em] text-[#527408]">
                  Four bounded verdicts
                </p>
                <h2 className="mt-4 font-display text-4xl font-bold tracking-[-0.045em] sm:text-5xl">
                  Designed to slow down the wrong certainty.
                </h2>
              </div>
              <p className="max-w-md leading-7 text-[#5a6572]">
                A completed review can be useful even when the answer is “not enough evidence.”
                Teams can opt into CI failure with repeatable <code>--fail-on</code> flags.
              </p>
            </div>

            <div className="mt-14 grid gap-4 md:grid-cols-2">
              {verdicts.map((verdict) => (
                <article key={verdict.name} className="rounded-3xl border border-[#0b1728]/10 bg-white p-6 sm:p-8">
                  <span
                    className={`inline-flex max-w-full break-all rounded-2xl px-3 py-1.5 text-left font-mono text-[11px] font-bold leading-5 ${verdict.tone}`}
                  >
                    {verdict.name}
                  </span>
                  <p className="mt-6 text-lg font-semibold leading-7">{verdict.summary}</p>
                  <p className="mt-3 leading-7 text-[#65707d]">
                    <span className="font-semibold text-[#0b1728]">Next:</span> {verdict.next}
                  </p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="bg-white">
          <div className="mx-auto max-w-7xl px-5 py-20 sm:px-8 sm:py-28 lg:px-10">
            <div className="grid gap-12 lg:grid-cols-[0.72fr_1.28fr]">
              <div>
                <p className="font-mono text-xs font-semibold uppercase tracking-[0.2em] text-[#527408]">
                  Where it fits
                </p>
                <h2 className="mt-4 font-display text-4xl font-bold tracking-[-0.045em] sm:text-5xl">
                  A narrow wedge, on purpose.
                </h2>
                <p className="mt-5 leading-7 text-[#5a6572]">
                  IndexPilot complements mature migration linters, index advisers, and database
                  monitoring. It owns the review checkpoint for an index somebody already wants to
                  merge.
                </p>
              </div>

              <div className="overflow-hidden rounded-3xl border border-[#0b1728]/15">
                <div className="grid grid-cols-[0.78fr_1.22fr] border-b border-[#0b1728]/10 bg-[#f7f5ee] px-5 py-4 font-mono text-[10px] font-bold uppercase tracking-[0.16em] text-[#65707d] sm:px-7">
                  <span>Tool category</span>
                  <span>The question it answers</span>
                </div>
                {[
                  ["Migration linter", "Is this DDL operationally safe to run?"],
                  ["Index adviser", "What indexes might improve this workload?"],
                  ["IndexPilot", "Does this exact migration index have enough evidence to benchmark?"],
                ].map(([category, question], index) => (
                  <div
                    key={category}
                    className={`grid grid-cols-[0.78fr_1.22fr] gap-5 px-5 py-5 sm:px-7 ${
                      index < 2 ? "border-b border-[#0b1728]/10" : "bg-[#b8f34a]"
                    }`}
                  >
                    <span className="font-bold">{category}</span>
                    <span className={index < 2 ? "text-[#5a6572]" : "font-semibold"}>{question}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section className="bg-[#0b1728] text-[#f7f5ee]">
          <div className="mx-auto grid max-w-7xl gap-10 px-5 py-20 sm:px-8 sm:py-24 lg:grid-cols-[0.85fr_1.15fr] lg:items-center lg:px-10">
            <div>
              <ShieldCheck className="h-9 w-9 text-[#b8f34a]" />
              <h2 className="mt-6 font-display text-4xl font-bold tracking-[-0.045em]">
                Read-only is a product boundary, not a footnote.
              </h2>
            </div>
            <ul className="grid gap-4 text-[#cad3de] sm:grid-cols-2">
              {[
                "Never creates, drops, or reindexes a physical index",
                "Parses migration SQL locally",
                "Uses EXPLAIN, never EXPLAIN ANALYZE",
                "Resets session-local HypoPG state",
                "Excludes raw workload SQL from reports",
                "Rejects unsupported index shapes clearly",
              ].map((boundary) => (
                <li key={boundary} className="flex gap-3 border-t border-white/10 pt-4">
                  <Check className="mt-0.5 h-4 w-4 shrink-0 text-[#b8f34a]" />
                  <span>{boundary}</span>
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section id="team-preview" className="border-b border-[#0b1728]/10 bg-[#f7f5ee]">
          <div className="mx-auto max-w-7xl px-5 py-20 sm:px-8 sm:py-24 lg:px-10">
            <div className="grid gap-10 lg:grid-cols-[0.8fr_1.2fr] lg:items-start">
              <div>
                <p className="font-mono text-xs font-semibold uppercase tracking-[0.2em] text-[#527408]">
                  Team workflow dipstick
                </p>
                <h2 className="mt-4 font-display text-4xl font-bold tracking-[-0.045em] sm:text-5xl">
                  Tell us where repeated index review breaks.
                </h2>
                <p className="mt-5 text-lg leading-8 text-[#536070]">
                  The CLI and Action exist today. Shared policy, pull-request summaries, and retained
                  team decisions are still a hypothesis. One public form now tests that gap with real,
                  sanitized workflows.
                </p>
                <div className="mt-7 flex flex-wrap gap-3">
                  <a
                    href={teamPreviewUrl}
                    className="inline-flex items-center gap-2 rounded-full bg-[#0b1728] px-5 py-3 text-sm font-bold text-[#f7f5ee]"
                  >
                    Share a team pain <ArrowUpRight className="h-4 w-4" />
                  </a>
                  <a
                    href={teamPreviewPlanUrl}
                    className="inline-flex items-center gap-2 rounded-full border border-[#0b1728] px-5 py-3 text-sm font-bold"
                  >
                    See the evidence gates <ArrowUpRight className="h-4 w-4" />
                  </a>
                </div>
              </div>

              <div className="overflow-hidden rounded-3xl border border-[#0b1728]/15 bg-white">
                <div className="grid gap-px bg-[#0b1728]/10 sm:grid-cols-3">
                  {[
                    ["Current", "Free advisory CLI and Action"],
                    ["Hypothesis", "Repeatable team policy and decision history"],
                    ["Actual asks", "Aggregate fixed choices in the public rollup"],
                  ].map(([label, value]) => (
                    <div key={label} className="bg-white p-6">
                      <p className="font-mono text-[10px] font-bold uppercase tracking-[0.16em] text-[#6b7582]">
                        {label}
                      </p>
                      <p className="mt-3 text-sm font-semibold leading-6">{value}</p>
                    </div>
                  ))}
                </div>
                <p className="p-6 text-xs leading-5 text-[#65707d] sm:p-8">
                  Follow live project activity, then tell us which repeated team pain should shape
                  the next upgrade.
                </p>
              </div>
            </div>
          </div>
        </section>

        <section className="bg-[#b8f34a] text-[#0b1728]">
          <div className="mx-auto flex max-w-7xl flex-col gap-8 px-5 py-16 sm:px-8 sm:py-20 lg:flex-row lg:items-center lg:justify-between lg:px-10">
            <div className="max-w-3xl">
              <p className="font-mono text-xs font-bold uppercase tracking-[0.2em]">Open source · read only</p>
              <h2 className="mt-3 font-display text-4xl font-bold tracking-[-0.045em] sm:text-5xl">
                Put one proposed index on trial.
              </h2>
            </div>
            <div className="flex flex-col gap-3 sm:flex-row">
              <a
                href={installationUrl}
                className="inline-flex items-center justify-center gap-2 rounded-full bg-[#0b1728] px-6 py-3.5 text-sm font-bold text-[#f7f5ee]"
              >
                Get started <ArrowRight className="h-4 w-4" />
              </a>
              <a
                href={teamPreviewUrl}
                className="inline-flex items-center justify-center gap-2 rounded-full border border-[#0b1728] px-6 py-3.5 text-sm font-bold"
              >
                Share a team pain <ArrowUpRight className="h-4 w-4" />
              </a>
            </div>
          </div>
        </section>
      </main>

      <footer className="bg-[#07101d] text-[#aeb9c7]">
        <div className="mx-auto flex max-w-7xl flex-col gap-8 px-5 py-10 sm:px-8 md:flex-row md:items-center md:justify-between lg:px-10">
          <div className="flex items-center gap-3">
            <BrandMark className="h-9 w-9" />
            <div>
              <p className="font-display font-bold text-[#f7f5ee]">IndexPilot</p>
              <p className="text-sm">Built in the open under the MIT License.</p>
              <p className="mt-1 text-xs">Cookie-free website analytics. No product-usage telemetry.</p>
            </div>
          </div>
          <nav className="flex flex-wrap gap-x-6 gap-y-3 text-sm" aria-label="Footer navigation">
            <a href={usageUrl} className="hover:text-[#f7f5ee]">Docs</a>
            <a href={`${repositoryUrl}/blob/main/SECURITY.md`} className="hover:text-[#f7f5ee]">Security</a>
            <a href={`${repositoryUrl}/blob/main/CONTRIBUTING.md`} className="hover:text-[#f7f5ee]">Contributing</a>
            <a href={teamPreviewPlanUrl} className="hover:text-[#f7f5ee]">Team preview</a>
            <a href={`${repositoryUrl}/discussions/categories/q-a`} className="hover:text-[#f7f5ee]">Help</a>
            <a href={`${repositoryUrl}/issues`} className="hover:text-[#f7f5ee]">Issues</a>
          </nav>
        </div>
      </footer>
    </div>
  );
}
