import Link from "next/link";
import {
  MessageSquare,
  BarChart3,
  AlertTriangle,
  Clock,
  ShieldCheck,
  CheckCircle,
  Database,
  ArrowRight,
} from "lucide-react";

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-slate-950 text-white selection:bg-indigo-500 selection:text-white">
      {/* Navigation */}
      <nav className="border-b border-slate-800/80 bg-slate-950/70 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center font-bold text-white shadow-lg shadow-indigo-500/20">
              BI
            </div>
            <span className="font-semibold text-base tracking-tight text-white">
              AI BI Agent
            </span>
          </div>

          <div className="flex items-center gap-4">
            <Link
              href="/login"
              className="text-sm font-medium text-slate-300 hover:text-white transition-colors"
            >
              Sign In
            </Link>
            <Link
              href="/signup"
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium rounded-lg shadow-sm transition-all"
            >
              Get Started
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="pt-24 pb-20 px-6 max-w-5xl mx-auto text-center">
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-indigo-500/30 bg-indigo-500/10 text-indigo-400 text-xs font-medium mb-8">
          <ShieldCheck className="w-4 h-4" />
          <span>Zero-Hallucination Deterministic SQL Intelligence</span>
        </div>

        <h1 className="text-4xl sm:text-6xl font-extrabold tracking-tight text-white mb-6 leading-[1.15]">
          Turn your business data into actionable answers with an{" "}
          <span className="bg-gradient-to-r from-indigo-400 via-purple-300 to-indigo-300 bg-clip-text text-transparent">
            Autonomous AI Agent
          </span>
        </h1>

        <p className="text-lg text-slate-400 max-w-2xl mx-auto mb-10 leading-relaxed">
          Connect your PostgreSQL databases or spreadsheets. Ask complex business questions in natural language, generate validated visualizations, and catch unusual trends without writing manual SQL.
        </p>

        <div className="flex items-center justify-center gap-4">
          <Link
            href="/signup"
            className="flex items-center gap-2 px-6 py-3 bg-indigo-600 hover:bg-indigo-500 text-white font-medium rounded-xl shadow-lg shadow-indigo-600/30 transition-all text-sm"
          >
            <span>Start Free Workspace</span>
            <ArrowRight className="w-4 h-4" />
          </Link>
          <Link
            href="/login"
            className="px-6 py-3 border border-slate-700 hover:border-slate-500 text-slate-300 hover:text-white font-medium rounded-xl transition-all text-sm"
          >
            Explore Demo
          </Link>
        </div>
      </section>

      {/* Feature Grid */}
      <section className="py-20 border-t border-slate-800/60 max-w-7xl mx-auto px-6">
        <div className="text-center mb-16">
          <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-white mb-3">
            Built for security, accuracy, and operational scale
          </h2>
          <p className="text-sm text-slate-400 max-w-xl mx-auto">
            Unlike chatbots that hallucinate numbers, our agent parses your schema, enforces strict read-only queries, and validates data mathematically.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <div className="p-6 rounded-2xl border border-slate-800 bg-slate-900/40 hover:border-slate-700 transition-all">
            <div className="w-10 h-10 rounded-xl bg-indigo-500/10 text-indigo-400 flex items-center justify-center mb-4">
              <MessageSquare className="w-5 h-5" />
            </div>
            <h3 className="text-base font-semibold text-white mb-2">Natural Language Queries</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Ask &quot;What were total sales this month compared to last month?&quot; The agent produces validated SQL, executes with statement timeouts, and returns traceable provenance.
            </p>
          </div>

          <div className="p-6 rounded-2xl border border-slate-800 bg-slate-900/40 hover:border-slate-700 transition-all">
            <div className="w-10 h-10 rounded-xl bg-emerald-500/10 text-emerald-400 flex items-center justify-center mb-4">
              <BarChart3 className="w-5 h-5" />
            </div>
            <h3 className="text-base font-semibold text-white mb-2">Smart Chart Recommendations</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Automatically selects the best visualization—time-series line charts, categorical bar charts, or KPI cards—straight from real query result structures.
            </p>
          </div>

          <div className="p-6 rounded-2xl border border-slate-800 bg-slate-900/40 hover:border-slate-700 transition-all">
            <div className="w-10 h-10 rounded-xl bg-amber-500/10 text-amber-400 flex items-center justify-center mb-4">
              <AlertTriangle className="w-5 h-5" />
            </div>
            <h3 className="text-base font-semibold text-white mb-2">Statistical Anomaly Detection</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Continuously monitors key metrics using Z-score and Interquartile Range (IQR) baselines to flag unexpected revenue drops or transaction spikes.
            </p>
          </div>

          <div className="p-6 rounded-2xl border border-slate-800 bg-slate-900/40 hover:border-slate-700 transition-all">
            <div className="w-10 h-10 rounded-xl bg-cyan-500/10 text-cyan-400 flex items-center justify-center mb-4">
              <Database className="w-5 h-5" />
            </div>
            <h3 className="text-base font-semibold text-white mb-2">Multi-Source Ingestion</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Upload CSV and Excel spreadsheets or connect production PostgreSQL databases with Fernet-encrypted credentials and automated schema profiling.
            </p>
          </div>

          <div className="p-6 rounded-2xl border border-slate-800 bg-slate-900/40 hover:border-slate-700 transition-all">
            <div className="w-10 h-10 rounded-xl bg-purple-500/10 text-purple-400 flex items-center justify-center mb-4">
              <Clock className="w-5 h-5" />
            </div>
            <h3 className="text-base font-semibold text-white mb-2">Automated Workflows</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Schedule recurring weekly executive summaries or daily anomaly scans via Celery and Redis with persistent run histories and retry policies.
            </p>
          </div>

          <div className="p-6 rounded-2xl border border-slate-800 bg-slate-900/40 hover:border-slate-700 transition-all">
            <div className="w-10 h-10 rounded-xl bg-rose-500/10 text-rose-400 flex items-center justify-center mb-4">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <h3 className="text-base font-semibold text-white mb-2">Enterprise Tenancy & Audit</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Strict multi-tenant row isolation, role-based access control (RBAC), and immutable audit logs capturing every rejected and successful query.
            </p>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-slate-800/80 py-10 px-6 text-center text-xs text-slate-500">
        <p>© 2026 AI Business Intelligence Agent SaaS. Production-grade data platform.</p>
      </footer>
    </div>
  );
}
