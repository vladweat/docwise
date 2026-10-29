"use client";

import Image from "next/image";
import Link from "next/link";
import {
  ArrowRight,
  FileSearch,
  LockKeyhole,
  Quote,
  SearchCheck,
  ShieldCheck,
  Sparkles,
  Workflow,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { useI18n } from "@/i18n/locale-provider";
import type { MessageKey } from "@/i18n/messages";

const CAPABILITIES: { title: MessageKey; body: MessageKey; icon: typeof LockKeyhole }[] = [
  {
    title: "landing.capabilityAccessTitle",
    body: "landing.capabilityAccessText",
    icon: ShieldCheck,
  },
  {
    title: "landing.capabilitySearchTitle",
    body: "landing.capabilitySearchText",
    icon: SearchCheck,
  },
  {
    title: "landing.capabilitySourcesTitle",
    body: "landing.capabilitySourcesText",
    icon: Quote,
  },
];

export function WelcomePage({ demoAvailable }: { demoAvailable: boolean }) {
  const { t } = useI18n();
  const demoHref = demoAvailable ? "/login?mode=demo" : "/login";

  return (
    <main className="relative isolate min-h-0 flex-1 overflow-y-auto bg-slate-950 text-slate-50">
      <div
        className="pointer-events-none absolute inset-x-0 top-14 -z-10 h-[34rem] bg-[radial-gradient(ellipse_at_50%_0%,rgba(37,99,235,0.18),transparent_68%)]"
        aria-hidden="true"
      />

      <section className="relative mx-auto grid w-full max-w-7xl items-center gap-12 px-4 pb-16 pt-12 sm:px-6 md:grid-cols-[0.9fr_1.1fr] md:gap-10 md:px-8 md:pb-24 md:pt-20">
        <div className="relative z-10">
          <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-blue-400/20 bg-blue-400/10 px-3 py-1.5 text-xs font-medium text-blue-200 sm:text-sm">
            <Sparkles className="size-4" aria-hidden="true" />
            {t("landing.eyebrow")}
          </div>
          <h1 className="max-w-2xl text-4xl font-semibold leading-[1.08] tracking-tight text-white sm:text-5xl lg:text-6xl">
            {t("landing.title")}
          </h1>
          <p className="mt-6 max-w-xl text-base leading-7 text-slate-300 sm:text-lg sm:leading-8">
            {t("landing.intro")}
          </p>

          <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:items-center">
            <Button asChild size="lg" className="h-12 px-5 text-base">
              <Link href={demoHref}>
                {t(demoAvailable ? "landing.demoCta" : "landing.signInCta")}
                <ArrowRight className="ml-2 size-4" aria-hidden="true" />
              </Link>
            </Button>
            {demoAvailable ? (
              <Button asChild variant="outline" size="lg" className="h-12 px-5 text-base">
                <Link href="/login?mode=standard">{t("landing.signInCta")}</Link>
              </Button>
            ) : null}
          </div>

          <ul className="mt-8 flex flex-wrap gap-x-5 gap-y-3 text-sm text-slate-400">
            {(["landing.trustPdf", "landing.trustAcl", "landing.trustSources"] as const).map((key) => (
              <li key={key} className="flex items-center gap-2">
                <span className="size-1.5 rounded-full bg-blue-400" aria-hidden="true" />
                {t(key)}
              </li>
            ))}
          </ul>
        </div>

        <figure className="relative z-10 mx-auto w-full max-w-3xl">
          <div className="absolute -inset-3 rounded-[2rem] bg-blue-500/10 blur-2xl" aria-hidden="true" />
          <div className="relative overflow-hidden rounded-2xl border border-slate-700/80 bg-slate-900 shadow-2xl shadow-black/50 sm:rounded-3xl">
            <Image
              src="/marketing/chat-citation.png"
              alt={t("landing.heroAlt")}
              width={2880}
              height={1800}
              priority
              sizes="(max-width: 768px) 100vw, 54vw"
              className="h-auto w-full"
            />
            <figcaption className="flex items-center gap-2 border-t border-slate-700/80 bg-slate-900/95 px-4 py-3 text-xs text-slate-300 sm:px-5 sm:text-sm">
              <Quote className="size-4 shrink-0 text-blue-300" aria-hidden="true" />
              {t("landing.previewLabel")}
            </figcaption>
          </div>
        </figure>
      </section>

      <section id="demo-flow" className="border-y border-slate-800/80 bg-slate-900/40">
        <div className="mx-auto grid max-w-7xl gap-10 px-4 py-16 sm:px-6 md:grid-cols-[0.85fr_1.15fr] md:items-center md:px-8 md:py-24">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.16em] text-blue-300">
              {t("landing.proofEyebrow")}
            </p>
            <h2 className="mt-4 text-3xl font-semibold leading-tight tracking-tight text-white sm:text-4xl">
              {t("landing.proofTitle")}
            </h2>
            <p className="mt-4 max-w-xl leading-7 text-slate-300">{t("landing.proofIntro")}</p>

            <div className="mt-8 space-y-4">
              <article className="rounded-xl border border-slate-700/80 bg-slate-950/70 p-4 sm:p-5">
                <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-amber-200">
                  <LockKeyhole className="size-4" aria-hidden="true" />
                  {t("landing.employeeLabel")}
                </div>
                <h3 className="mt-3 font-semibold text-white">{t("landing.employeeTitle")}</h3>
                <p className="mt-1 text-sm leading-6 text-slate-400">{t("landing.employeeText")}</p>
              </article>
              <article className="rounded-xl border border-blue-400/30 bg-blue-400/[0.06] p-4 sm:p-5">
                <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-blue-200">
                  <Quote className="size-4" aria-hidden="true" />
                  {t("landing.hrLabel")}
                </div>
                <h3 className="mt-3 font-semibold text-white">{t("landing.hrTitle")}</h3>
                <p className="mt-1 text-sm leading-6 text-slate-300">{t("landing.hrText")}</p>
              </article>
            </div>

            {demoAvailable ? (
              <Link
                href={demoHref}
                className="mt-6 inline-flex items-center gap-2 text-sm font-semibold text-blue-300 hover:text-blue-200 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-blue-300"
              >
                {t("landing.demoCta")}
                <ArrowRight className="size-4" aria-hidden="true" />
              </Link>
            ) : null}
          </div>

          <figure className="overflow-hidden rounded-2xl border border-slate-700/80 bg-slate-950 shadow-xl shadow-black/30">
            <Image
              src="/marketing/acl-refusal.png"
              alt={t("landing.refusalAlt")}
              width={2880}
              height={1800}
              sizes="(max-width: 768px) 100vw, 55vw"
              className="h-auto w-full"
            />
            <figcaption className="border-t border-slate-800 px-4 py-3 text-xs text-slate-400 sm:px-5 sm:text-sm">
              {t("landing.refusalAlt")}
            </figcaption>
          </figure>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-16 sm:px-6 md:px-8 md:py-24">
        <div className="mx-auto max-w-3xl text-center">
          <p className="text-sm font-semibold uppercase tracking-[0.16em] text-blue-300">
            {t("landing.capabilitiesEyebrow")}
          </p>
          <h2 className="mt-4 text-3xl font-semibold leading-tight tracking-tight text-white sm:text-4xl">
            {t("landing.capabilitiesTitle")}
          </h2>
        </div>
        <div className="mt-10 grid gap-4 md:grid-cols-3">
          {CAPABILITIES.map(({ title, body, icon: Icon }) => (
            <article
              key={title}
              className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 sm:p-6"
            >
              <div className="flex size-11 items-center justify-center rounded-xl border border-blue-400/20 bg-blue-400/10 text-blue-300">
                <Icon className="size-5" aria-hidden="true" />
              </div>
              <h3 className="mt-5 text-lg font-semibold text-white">{t(title)}</h3>
              <p className="mt-2 text-sm leading-6 text-slate-400">{t(body)}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="border-y border-slate-800/80 bg-slate-900/40">
        <div className="mx-auto grid max-w-7xl gap-10 px-4 py-16 sm:px-6 md:grid-cols-[1.1fr_0.9fr] md:items-center md:px-8 md:py-20">
          <figure className="order-2 overflow-hidden rounded-2xl border border-slate-700/80 bg-slate-950 shadow-xl shadow-black/30 md:order-1">
            <Image
              src="/marketing/search-inspect.png"
              alt={t("landing.inspectAlt")}
              width={2880}
              height={1800}
              sizes="(max-width: 768px) 100vw, 55vw"
              className="h-auto w-full"
            />
            <figcaption className="border-t border-slate-800 px-4 py-3 text-xs text-slate-400 sm:px-5 sm:text-sm">
              {t("landing.inspectAlt")}
            </figcaption>
          </figure>
          <div className="order-1 md:order-2">
            <p className="flex items-center gap-2 text-sm font-semibold uppercase tracking-[0.16em] text-blue-300">
              <FileSearch className="size-4" aria-hidden="true" />
              {t("landing.inspectEyebrow")}
            </p>
            <h2 className="mt-4 text-3xl font-semibold leading-tight tracking-tight text-white sm:text-4xl">
              {t("landing.inspectTitle")}
            </h2>
            <p className="mt-4 leading-7 text-slate-300">{t("landing.inspectText")}</p>
            <div className="mt-6 inline-flex items-center gap-2 rounded-full border border-slate-700 bg-slate-950/60 px-3 py-2 text-sm text-slate-300">
              <Workflow className="size-4 text-blue-300" aria-hidden="true" />
              Dense + FTS <span aria-hidden="true">→</span> RRF <span aria-hidden="true">→</span> Rerank
            </div>
          </div>
        </div>
      </section>

      <section className="px-4 py-16 sm:px-6 md:py-24">
        <div className="mx-auto max-w-4xl rounded-3xl border border-blue-400/20 bg-[linear-gradient(135deg,rgba(30,58,138,0.38),rgba(15,23,42,0.92)_55%)] px-5 py-10 text-center shadow-2xl shadow-black/20 sm:px-10 sm:py-14">
          <div className="mx-auto flex size-12 items-center justify-center rounded-2xl border border-blue-300/25 bg-blue-300/10 text-blue-200">
            <Sparkles className="size-5" aria-hidden="true" />
          </div>
          <h2 className="mt-5 text-3xl font-semibold tracking-tight text-white sm:text-4xl">
            {t("landing.finalTitle")}
          </h2>
          <p className="mx-auto mt-4 max-w-2xl leading-7 text-slate-300">{t("landing.finalText")}</p>
          <div className="mt-7 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Button asChild size="lg" className="h-12 px-5 text-base">
              <Link href={demoHref}>
                {t(demoAvailable ? "landing.finalCta" : "landing.signInCta")}
                <ArrowRight className="ml-2 size-4" aria-hidden="true" />
              </Link>
            </Button>
            {demoAvailable ? (
              <Button asChild variant="outline" size="lg" className="h-12 px-5 text-base">
                <Link href="/login?mode=standard">{t("landing.signInCta")}</Link>
              </Button>
            ) : null}
          </div>
          <p className="mt-5 text-xs text-slate-500">{t("landing.footnote")}</p>
        </div>
      </section>

      <footer className="border-t border-slate-800 px-4 py-6 sm:px-6">
        <div className="mx-auto flex max-w-7xl flex-col gap-2 text-xs text-slate-500 sm:flex-row sm:items-center sm:justify-between">
          <span className="font-semibold tracking-wide text-slate-300">Docwise</span>
          <span>{t("landing.footerProduct")}</span>
        </div>
      </footer>
    </main>
  );
}
