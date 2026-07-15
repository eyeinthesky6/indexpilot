import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { ArrowLeft, ArrowRight, Check, Github, Terminal } from "lucide-react";
import { findUseCase, useCases } from "../useCases";

const siteUrl = "https://eyeinthesky6.github.io/indexpilot";
const repositoryUrl = "https://github.com/eyeinthesky6/indexpilot";

export function generateStaticParams() { return useCases.map(({ slug }) => ({ slug })); }

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const useCase = findUseCase((await params).slug);
  if (!useCase) return {};
  const url = `${siteUrl}/use-cases/${useCase.slug}/`;
  return { title: useCase.title, description: useCase.description, alternates: { canonical: url }, openGraph: { title: useCase.title, description: useCase.description, url, type: "article" } };
}

export default async function UseCasePage({ params }: { params: Promise<{ slug: string }> }) {
  const useCase = findUseCase((await params).slug);
  if (!useCase) notFound();
  const structuredData = { "@context": "https://schema.org", "@type": "TechArticle", headline: useCase.title, description: useCase.description, mainEntityOfPage: `${siteUrl}/use-cases/${useCase.slug}/`, about: { "@type": "SoftwareApplication", name: "IndexPilot", applicationCategory: "DeveloperApplication" } };
  return (
    <main className="min-h-screen bg-[#f7f5ee] text-[#0b1728]">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(structuredData) }} />
      <article className="mx-auto max-w-4xl px-5 py-14 sm:px-8 sm:py-20">
        <a href={`${siteUrl}/`} className="inline-flex items-center gap-2 text-sm font-bold text-[#456b00]"><ArrowLeft className="h-4 w-4" /> IndexPilot</a>
        <p className="mt-12 font-mono text-xs font-bold uppercase tracking-[0.16em] text-[#456b00]">PostgreSQL index decision guide</p>
        <h1 className="mt-4 font-display text-4xl font-bold tracking-[-0.045em] sm:text-6xl">{useCase.title}</h1>
        <p className="mt-7 max-w-3xl text-xl leading-9 text-[#435064]">{useCase.description}</p>
        <section className="mt-12 rounded-3xl bg-[#0b1728] p-7 text-[#f7f5ee] sm:p-10">
          <h2 className="font-display text-2xl font-bold">The problem</h2><p className="mt-4 text-lg leading-8 text-[#cbd4df]">{useCase.question}</p>
          <h2 className="mt-9 font-display text-2xl font-bold">How IndexPilot helps</h2><p className="mt-4 text-lg leading-8 text-[#cbd4df]">{useCase.answer}</p>
        </section>
        <section className="mt-12">
          <h2 className="font-display text-3xl font-bold">Try it</h2>
          <div className="mt-5 overflow-x-auto rounded-2xl border border-[#0b1728]/15 bg-white p-5 font-mono text-sm"><span className="text-[#456b00]">$</span> pipx install indexpilot<br /><span className="text-[#456b00]">$</span> {useCase.command}</div>
          <ul className="mt-7 grid gap-3">{useCase.evidence.map((item) => <li key={item} className="flex items-start gap-3"><Check className="mt-1 h-5 w-5 text-[#456b00]" /><span>{item}</span></li>)}</ul>
        </section>
        <section className="mt-14 border-t border-[#0b1728]/15 pt-10">
          <h2 className="font-display text-3xl font-bold">Important limit</h2>
          <p className="mt-4 text-lg leading-8 text-[#435064]">IndexPilot decides whether an index has enough evidence to benchmark. It does not claim that planner cost equals production latency or that an index is safe to ship.</p>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row"><a href={`${repositoryUrl}#quick-start`} className="inline-flex items-center justify-center gap-2 rounded-full bg-[#b8f34a] px-6 py-3 font-bold">Review a migration <ArrowRight className="h-4 w-4" /></a><a href={repositoryUrl} className="inline-flex items-center justify-center gap-2 rounded-full border border-[#0b1728] px-6 py-3 font-bold"><Github className="h-4 w-4" /> View on GitHub</a></div>
        </section>
        <aside className="mt-16 rounded-2xl border border-[#0b1728]/10 p-6"><p className="flex items-center gap-2 font-bold"><Terminal className="h-4 w-4" /> Other PostgreSQL index questions</p><ul className="mt-4 grid gap-2">{useCases.filter((item) => item.slug !== useCase.slug).map((item) => <li key={item.slug}><a className="text-[#456b00] underline decoration-[#456b00]/30 underline-offset-4" href={`${siteUrl}/use-cases/${item.slug}/`}>{item.title}</a></li>)}</ul></aside>
      </article>
    </main>
  );
}
