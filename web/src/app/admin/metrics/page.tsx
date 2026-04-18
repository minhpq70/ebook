'use client';
import { useEffect, useState, useCallback } from 'react';
import { adminAPI } from '@/lib/auth';
import { Activity, AlertTriangle, BarChart3, RefreshCw, Trash2, ArrowLeft, Cpu, HardDrive, Zap } from 'lucide-react';
import Link from 'next/link';

/* eslint-disable @typescript-eslint/no-explicit-any */

export default function MetricsDashboard() {
    const [runtime, setRuntime] = useState<any>(null);
    const [summary, setSummary] = useState<any>(null);
    const [analytics, setAnalytics] = useState<any>(null);
    const [errorsData, setErrorsData] = useState<{ errors: any[]; summary: any } | null>(null);
    const [loading, setLoading] = useState(true);
    const [tab, setTab] = useState<'overview' | 'errors'>('overview');

    const fetchAll = useCallback(async () => {
        setLoading(true);
        try {
            const [r, s, a, e] = await Promise.all([
                adminAPI.getRuntime(),
                adminAPI.getSummary(),
                adminAPI.getAnalytics(),
                adminAPI.getErrors(50),
            ]);
            setRuntime(r);
            setSummary(s);
            setAnalytics(a);
            setErrorsData(e);
        } catch (err) {
            console.error('Failed to fetch metrics:', err);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { fetchAll(); }, [fetchAll]);

    // Auto-refresh every 30s
    useEffect(() => {
        const interval = setInterval(fetchAll, 30000);
        return () => clearInterval(interval);
    }, [fetchAll]);

    const handleClearErrors = async () => {
        if (!confirm('Xác nhận xóa toàn bộ buffer lỗi?')) return;
        await adminAPI.clearErrors();
        fetchAll();
    };

    const mem = runtime?.memory;
    const cb = runtime?.circuit_breaker;

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <Link href="/admin" className="text-[#8890a4] hover:text-white transition-colors">
                        <ArrowLeft className="w-5 h-5" />
                    </Link>
                    <h1 className="text-xl font-bold text-white flex items-center gap-2">
                        <BarChart3 className="w-5 h-5 text-[#6c63ff]" /> Dashboard Giám Sát
                    </h1>
                </div>
                <button
                    onClick={fetchAll}
                    disabled={loading}
                    className="flex items-center gap-1.5 bg-[#6c63ff] text-white text-sm font-medium py-2 px-4 rounded-lg border-none cursor-pointer disabled:opacity-50 hover:bg-[#8b85ff] transition-colors"
                >
                    <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} /> Refresh
                </button>
            </div>

            {/* Tabs */}
            <div className="flex gap-1 bg-[#1a1d27] p-1 rounded-lg w-fit">
                {(['overview', 'errors'] as const).map(t => (
                    <button key={t} onClick={() => setTab(t)}
                        className={`py-1.5 px-4 rounded-md text-sm font-medium border-none cursor-pointer transition-all ${tab === t ? 'bg-[#6c63ff] text-white' : 'bg-transparent text-[#8890a4] hover:text-white'
                            }`}
                    >{t === 'overview' ? '📊 Tổng quan' : `🚨 Lỗi (${errorsData?.summary?.total_errors || 0})`}</button>
                ))}
            </div>

            {loading && !runtime ? (
                <div className="text-center py-16 text-[#8890a4]">Đang tải metrics...</div>
            ) : tab === 'overview' ? (
                <OverviewTab runtime={runtime} summary={summary} analytics={analytics} mem={mem} cb={cb} />
            ) : (
                <ErrorsTab errorsData={errorsData} onClear={handleClearErrors} />
            )}
        </div>
    );
}

function StatCard({ icon: Icon, label, value, sub, color = '#6c63ff' }: {
    icon: any; label: string; value: string | number; sub?: string; color?: string;
}) {
    return (
        <div className="bg-[#1e2130] rounded-xl border border-[#2d3148] p-4">
            <div className="flex items-center gap-2 mb-2">
                <Icon className="w-4 h-4" style={{ color }} />
                <span className="text-xs text-[#8890a4] uppercase tracking-wider">{label}</span>
            </div>
            <div className="text-2xl font-bold text-white">{value}</div>
            {sub && <div className="text-xs text-[#8890a4] mt-1">{sub}</div>}
        </div>
    );
}

function OverviewTab({ runtime, summary, analytics, mem, cb }: any) {
    const reqMetrics = summary?.request_metrics;
    const queryMetrics = summary?.query_metrics;
    const cacheMetrics = summary?.cache_metrics;

    return (
        <div className="space-y-6">
            {/* Memory cards */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <StatCard icon={HardDrive} label="Heap hiện tại" value={`${mem?.python_heap_mb || 0} MB`}
                    sub={`Peak: ${mem?.python_heap_peak_mb || 0} MB`} color="#34d399" />
                <StatCard icon={Cpu} label="Soft Limit" value={`${mem?.soft_limit_mb || 0} MB`}
                    sub={cb?.soft_limit_exceeded ? '⚠️ Đã vượt!' : '✅ OK'} color={cb?.soft_limit_exceeded ? '#fbbf24' : '#34d399'} />
                <StatCard icon={Cpu} label="Hard Limit" value={`${mem?.hard_limit_mb || 0} MB`}
                    sub={cb?.hard_limit_exceeded ? '🔴 ĐÃ VƯỢT!' : '✅ OK'} color={cb?.hard_limit_exceeded ? '#ef4444' : '#34d399'} />
                <StatCard icon={Zap} label="Circuit Breaker" value={cb?.enabled ? 'BẬT' : 'TẮT'}
                    color={cb?.enabled ? '#34d399' : '#8890a4'} />
            </div>

            {/* Request metrics */}
            {reqMetrics && (
                <div className="bg-[#1e2130] rounded-xl border border-[#2d3148] p-5">
                    <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
                        <Activity className="w-4 h-4 text-[#6c63ff]" /> Request Metrics
                    </h3>
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-center">
                        <div><div className="text-xl font-bold text-white">{reqMetrics.total_requests || 0}</div><div className="text-xs text-[#8890a4]">Tổng requests</div></div>
                        <div><div className="text-xl font-bold text-[#34d399]">{reqMetrics.success_count || 0}</div><div className="text-xs text-[#8890a4]">Thành công</div></div>
                        <div><div className="text-xl font-bold text-[#ef4444]">{reqMetrics.error_count || 0}</div><div className="text-xs text-[#8890a4]">Lỗi</div></div>
                        <div><div className="text-xl font-bold text-white">{typeof reqMetrics.avg_latency_ms === 'number' ? reqMetrics.avg_latency_ms.toFixed(0) : '—'} ms</div><div className="text-xs text-[#8890a4]">Avg latency</div></div>
                    </div>
                </div>
            )}

            {/* Query + Cache */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {queryMetrics && (
                    <div className="bg-[#1e2130] rounded-xl border border-[#2d3148] p-5">
                        <h3 className="text-sm font-semibold text-white mb-3">📚 Query RAG</h3>
                        <div className="space-y-2 text-sm">
                            <div className="flex justify-between"><span className="text-[#8890a4]">Tổng queries</span><span className="text-white font-medium">{queryMetrics.total_queries || 0}</span></div>
                            <div className="flex justify-between"><span className="text-[#8890a4]">Avg latency</span><span className="text-white font-medium">{typeof queryMetrics.avg_latency_ms === 'number' ? queryMetrics.avg_latency_ms.toFixed(0) : '—'} ms</span></div>
                            <div className="flex justify-between"><span className="text-[#8890a4]">Tokens used</span><span className="text-white font-medium">{queryMetrics.total_tokens || 0}</span></div>
                        </div>
                    </div>
                )}
                {cacheMetrics && (
                    <div className="bg-[#1e2130] rounded-xl border border-[#2d3148] p-5">
                        <h3 className="text-sm font-semibold text-white mb-3">💾 Cache</h3>
                        <div className="space-y-2 text-sm">
                            <div className="flex justify-between"><span className="text-[#8890a4]">Hits</span><span className="text-[#34d399] font-medium">{cacheMetrics.hits || 0}</span></div>
                            <div className="flex justify-between"><span className="text-[#8890a4]">Misses</span><span className="text-[#fbbf24] font-medium">{cacheMetrics.misses || 0}</span></div>
                            <div className="flex justify-between"><span className="text-[#8890a4]">Hit rate</span><span className="text-white font-medium">{typeof cacheMetrics.hit_rate === 'number' ? (cacheMetrics.hit_rate * 100).toFixed(1) : '—'}%</span></div>
                        </div>
                    </div>
                )}
            </div>

            {/* Analytics raw */}
            {analytics && (
                <details className="bg-[#1e2130] rounded-xl border border-[#2d3148] p-5">
                    <summary className="text-sm font-semibold text-white cursor-pointer">🔍 Analytics chi tiết (JSON)</summary>
                    <pre className="mt-3 text-xs text-[#8890a4] overflow-auto max-h-[300px] bg-[#0f1117] p-3 rounded-lg">
                        {JSON.stringify(analytics, null, 2)}
                    </pre>
                </details>
            )}
        </div>
    );
}

function ErrorsTab({ errorsData, onClear }: { errorsData: any; onClear: () => void }) {
    const errors = errorsData?.errors || [];
    const summary = errorsData?.summary || {};

    return (
        <div className="space-y-4">
            {/* Error summary */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                    <span className="text-sm text-[#8890a4]">
                        Tổng: <strong className="text-white">{summary.total_errors || 0}</strong> lỗi |
                        Buffer: <strong className="text-white">{summary.buffer_size || 0}</strong>/{summary.buffer_capacity || 200}
                    </span>
                    {summary.error_types && Object.keys(summary.error_types).length > 0 && (
                        <div className="flex gap-2">
                            {Object.entries(summary.error_types as Record<string, number>).slice(0, 5).map(([type, count]) => (
                                <span key={type} className="bg-[#ef4444]/10 text-[#ef4444] text-xs py-0.5 px-2 rounded-full">
                                    {type}: {count}
                                </span>
                            ))}
                        </div>
                    )}
                </div>
                {errors.length > 0 && (
                    <button onClick={onClear} className="flex items-center gap-1 text-xs text-[#ef4444] bg-[#ef4444]/10 border-none py-1.5 px-3 rounded-lg cursor-pointer hover:bg-[#ef4444]/20 transition-colors">
                        <Trash2 className="w-3 h-3" /> Xóa buffer
                    </button>
                )}
            </div>

            {/* Error list */}
            {errors.length === 0 ? (
                <div className="text-center py-16 text-[#8890a4]">
                    <AlertTriangle className="w-10 h-10 mx-auto mb-3 opacity-30" />
                    <p>Chưa có lỗi nào được ghi nhận</p>
                </div>
            ) : (
                <div className="space-y-2">
                    {errors.map((err: any, i: number) => (
                        <details key={i} className="bg-[#1e2130] rounded-xl border border-[#2d3148] p-4">
                            <summary className="flex items-center gap-3 cursor-pointer text-sm">
                                <span className={`w-2 h-2 rounded-full shrink-0 ${err.level === 'critical' ? 'bg-[#ef4444]' : 'bg-[#fbbf24]'}`} />
                                <span className="text-white font-medium truncate">{err.error_type}: {err.message?.slice(0, 80)}</span>
                                <span className="ml-auto text-xs text-[#8890a4] shrink-0">
                                    {err.method} {err.path} · {err.status_code}
                                </span>
                            </summary>
                            <div className="mt-3 space-y-2">
                                <div className="text-xs text-[#8890a4]">
                                    <strong>Time:</strong> {err.timestamp}
                                </div>
                                <div className="text-xs text-[#8890a4]">
                                    <strong>Message:</strong> {err.message}
                                </div>
                                {err.stack_trace && (
                                    <pre className="text-xs text-[#ef4444]/70 bg-[#0f1117] p-3 rounded-lg overflow-auto max-h-[200px]">
                                        {err.stack_trace}
                                    </pre>
                                )}
                            </div>
                        </details>
                    ))}
                </div>
            )}
        </div>
    );
}
