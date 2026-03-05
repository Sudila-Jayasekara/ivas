'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import {
    Clock,
    Search,
    ChevronRight,
    Calendar,
    Filter
} from 'lucide-react';
import Link from 'next/link';

export default function SessionsPage() {
    const [sessions, setSessions] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState('');

    useEffect(() => {
        const fetchSessions = async () => {
            try {
                // Assuming instructor "inst-001" for demo purposes based on mock data
                const data = await api.getInstructorAssessments('inst-001');
                setSessions(data);
            } catch (error) {
                console.error('Failed to fetch sessions', error);
            } finally {
                setLoading(false);
            }
        };
        fetchSessions();
    }, []);

    const filteredSessions = sessions.filter(s =>
        s.student_id?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        s.assignment_id?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        s.id?.toLowerCase().includes(searchQuery.toLowerCase())
    );

    return (
        <div className="space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-bold text-zinc-900 dark:text-white">Sessions Overview</h1>
                    <p className="text-zinc-500 dark:text-zinc-400 mt-1">Monitor all instructor assessment sessions and transcripts.</p>
                </div>
            </div>

            {/* Filters & Search */}
            <div className="flex flex-col md:flex-row gap-4">
                <div className="relative flex-1">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" size={18} />
                    <input
                        type="text"
                        placeholder="Search by student, assignment, or session ID..."
                        className="w-full pl-10 pr-4 py-2 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 dark:text-white"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                    />
                </div>
                <button className="inline-flex items-center gap-2 border border-zinc-200 dark:border-zinc-800 px-4 py-2 rounded-lg bg-white dark:bg-zinc-900 text-zinc-700 dark:text-zinc-300 hover:bg-zinc-50 dark:hover:bg-zinc-800 transition-colors">
                    <Filter size={18} />
                    <span>Filters</span>
                </button>
            </div>

            {/* Sessions Table */}
            <div className="bg-white dark:bg-zinc-900 rounded-2xl border border-zinc-200 dark:border-zinc-800 shadow-sm overflow-hidden">
                {loading ? (
                    <div className="p-12 text-center">
                        <div className="w-8 h-8 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
                        <p className="text-zinc-500">Loading sessions...</p>
                    </div>
                ) : filteredSessions.length > 0 ? (
                    <div className="overflow-x-auto">
                        <table className="w-full text-left">
                            <thead>
                                <tr className="border-b border-zinc-200 dark:border-zinc-800 bg-zinc-50/50 dark:bg-zinc-800/20">
                                    <th className="px-6 py-4 text-xs font-semibold text-zinc-500 uppercase tracking-wider">Date</th>
                                    <th className="px-6 py-4 text-xs font-semibold text-zinc-500 uppercase tracking-wider">Session ID</th>
                                    <th className="px-6 py-4 text-xs font-semibold text-zinc-500 uppercase tracking-wider">Student</th>
                                    <th className="px-6 py-4 text-xs font-semibold text-zinc-500 uppercase tracking-wider">Assignment</th>
                                    <th className="px-6 py-4 text-xs font-semibold text-zinc-500 uppercase tracking-wider">Status</th>
                                    <th className="px-6 py-4 text-xs font-semibold text-zinc-500 uppercase tracking-wider text-right">Review</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800 text-zinc-900 dark:text-zinc-100">
                                {filteredSessions.map((sess) => (
                                    <tr key={sess.id} className="hover:bg-zinc-50 dark:hover:bg-zinc-800/50 transition-colors group">
                                        <td className="px-6 py-4 text-sm whitespace-nowrap">
                                            <div className="flex items-center gap-2 text-zinc-600 dark:text-zinc-400">
                                                <Calendar size={14} />
                                                {new Date(sess.started_at).toLocaleString()}
                                            </div>
                                        </td>
                                        <td className="px-6 py-4 text-sm font-mono text-zinc-500">{sess.id}</td>
                                        <td className="px-6 py-4 text-sm font-medium">
                                            {sess.student_id}
                                        </td>
                                        <td className="px-6 py-4 text-sm text-zinc-600 dark:text-zinc-400">
                                            {sess.assignment_id}
                                        </td>
                                        <td className="px-6 py-4">
                                            <span className={`inline-flex items-center rounded-full px-2 py-1 text-xs font-medium ${sess.status === 'completed' ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-400' :
                                                sess.status === 'active' ? 'bg-blue-50 text-blue-700 dark:bg-blue-950/30 dark:text-blue-400' :
                                                    'bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-400'
                                                }`}>
                                                {sess.status}
                                            </span>
                                        </td>
                                        <td className="px-6 py-4 text-right">
                                            <Link
                                                href={`/viva/${sess.id}`}
                                                className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-zinc-100 hover:bg-indigo-100 dark:bg-zinc-800 dark:hover:bg-indigo-900 text-zinc-600 hover:text-indigo-600 dark:text-zinc-400 dark:hover:text-indigo-400 transition-colors"
                                            >
                                                <ChevronRight size={18} />
                                            </Link>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                ) : (
                    <div className="p-12 text-center">
                        <div className="w-16 h-16 bg-zinc-100 dark:bg-zinc-800 rounded-full flex items-center justify-center mx-auto mb-4">
                            <Clock size={24} className="text-zinc-400" />
                        </div>
                        <h3 className="text-lg font-semibold dark:text-white">No Sessions Found</h3>
                        <p className="text-zinc-500 max-w-sm mx-auto mt-2">No active or past assessments matched your current criteria.</p>
                    </div>
                )}
            </div>
        </div>
    );
}
