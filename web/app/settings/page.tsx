'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import {
    Settings,
    Cpu,
    Activity,
    RefreshCw,
    CheckCircle2,
    AlertCircle
} from 'lucide-react';

export default function SettingsPage() {
    const [providerInfo, setProviderInfo] = useState<any>(null);
    const [healthStatus, setHealthStatus] = useState<'loading' | 'healthy' | 'unhealthy'>('loading');
    const [switching, setSwitching] = useState(false);
    const [loading, setLoading] = useState(true);

    const fetchProviderData = async () => {
        setLoading(true);
        try {
            const info = await api.getProvider();
            setProviderInfo(info);

            const health = await api.getProviderHealth();
            setHealthStatus('healthy');
        } catch (error) {
            console.error('Failed to fetch provider info', error);
            setHealthStatus('unhealthy');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchProviderData();
    }, []);

    const handleSwitch = async (provider: string) => {
        if (provider === providerInfo?.active_provider) return;

        setSwitching(true);
        try {
            await api.switchProvider(provider);
            await fetchProviderData();
        } catch (error) {
            alert('Failed to switch provider');
        } finally {
            setSwitching(false);
        }
    };

    return (
        <div className="space-y-8">
            <div>
                <h1 className="text-3xl font-bold text-zinc-900 dark:text-white">Settings</h1>
                <p className="text-zinc-500 dark:text-zinc-400 mt-1">Configure the system and LLM backbone.</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                {/* LLM Configuration */}
                <div className="bg-white dark:bg-zinc-900 rounded-2xl border border-zinc-200 dark:border-zinc-800 shadow-sm overflow-hidden p-6 space-y-6">
                    <div className="flex items-center gap-3">
                        <div className="p-2 bg-indigo-50 dark:bg-indigo-950/30 text-indigo-600 rounded-lg">
                            <Cpu size={24} />
                        </div>
                        <h2 className="text-xl font-semibold text-zinc-900 dark:text-white">LLM Provider</h2>
                    </div>

                    {loading ? (
                        <div className="py-12 flex justify-center">
                            <RefreshCw className="animate-spin text-zinc-400" />
                        </div>
                    ) : (
                        <div className="space-y-4">
                            <div className="grid grid-cols-1 gap-3">
                                {providerInfo?.supported_providers.map((p: string) => (
                                    <button
                                        key={p}
                                        onClick={() => handleSwitch(p)}
                                        disabled={switching}
                                        className={`
                      flex items-center justify-between p-4 rounded-xl border transition-all
                      ${providerInfo.active_provider === p
                                                ? 'border-indigo-600 bg-indigo-50/50 dark:bg-indigo-950/20'
                                                : 'border-zinc-200 dark:border-zinc-800 hover:bg-zinc-50 dark:hover:bg-zinc-800'}
                    `}
                                    >
                                        <span className="font-medium capitalize text-zinc-900 dark:text-white">{p}</span>
                                        {providerInfo.active_provider === p && (
                                            <CheckCircle2 size={18} className="text-indigo-600" />
                                        )}
                                    </button>
                                ))}
                            </div>

                            <p className="text-xs text-zinc-500 font-medium italic">
                                {switching ? 'Hot-swapping provider...' : 'Changes take effect immediately without restart.'}
                            </p>
                        </div>
                    )}
                </div>

                {/* System Health */}
                <div className="bg-white dark:bg-zinc-900 rounded-2xl border border-zinc-200 dark:border-zinc-800 shadow-sm overflow-hidden p-6 space-y-6">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <div className="p-2 bg-emerald-50 dark:bg-emerald-950/30 text-emerald-600 rounded-lg">
                                <Activity size={24} />
                            </div>
                            <h2 className="text-xl font-semibold text-zinc-900 dark:text-white">System Health</h2>
                        </div>
                        <button
                            onClick={fetchProviderData}
                            className="p-2 text-zinc-400 hover:text-zinc-600 transition-colors"
                        >
                            <RefreshCw size={20} />
                        </button>
                    </div>

                    <div className="space-y-4">
                        <div className="flex items-center justify-between p-4 bg-zinc-50 dark:bg-zinc-800/50 rounded-xl">
                            <span className="text-sm font-medium text-zinc-600 dark:text-zinc-400">LLM Reachability</span>
                            {healthStatus === 'loading' ? (
                                <RefreshCw size={16} className="animate-spin text-zinc-400" />
                            ) : healthStatus === 'healthy' ? (
                                <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-emerald-600">
                                    <span className="w-2 h-2 bg-emerald-500 rounded-full"></span>
                                    Connected
                                </span>
                            ) : (
                                <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-red-600">
                                    <AlertCircle size={14} />
                                    Offline
                                </span>
                            )}
                        </div>

                        <div className="flex items-center justify-between p-4 bg-zinc-50 dark:bg-zinc-800/50 rounded-xl">
                            <span className="text-sm font-medium text-zinc-600 dark:text-zinc-400">Database Connection</span>
                            <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-emerald-600">
                                <span className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse"></span>
                                Active
                            </span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
