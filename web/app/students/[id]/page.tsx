'use client';

import { useParams } from 'next/navigation';
import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import {
    ArrowLeft,
    GraduationCap,
    TrendingUp,
    Clock,
    Activity,
    CheckCircle2,
    Calendar,
    ChevronRight,
    Loader2
} from 'lucide-react';
import Link from 'next/link';
import { Student } from '@/types';

export default function StudentDetailsPage() {
    const { id } = useParams();
    const [student, setStudent] = useState<Student | null>(null);
    const [progress, setProgress] = useState<any>(null);
    const [sessions, setSessions] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchStudentData = async () => {
            try {
                const s = await api.getStudent(id as string);
                setStudent(s);

                try {
                    const p = await api.getStudentProgress(id as string);
                    setProgress(p);
                } catch (e) {
                    console.warn('Progress data missing');
                }

                try {
                    const sess = await api.getStudentSessions(id as string);
                    setSessions(sess);
                } catch (e) {
                    console.warn('Session data missing');
                }
            } catch (error) {
                console.error('Failed to fetch student data', error);
            } finally {
                setLoading(false);
            }
        };
        fetchStudentData();
    }, [id]);

    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
                <Loader2 className="animate-spin text-indigo-600" size={32} />
                <p className="text-zinc-500 font-medium">Loading student profile...</p>
            </div>
        );
    }

    if (!student) {
        return (
            <div className="p-12 text-center text-zinc-500">
                Student not found.
            </div>
        );
    }

    return (
        <div className="space-y-8 pb-20">
            <Link href="/students" className="inline-flex items-center gap-2 text-zinc-500 hover:text-zinc-900 dark:hover:text-white transition-colors">
                <ArrowLeft size={18} />
                Back to Students
            </Link>

            <div className="flex flex-col lg:flex-row gap-8">
                {/* Left: Student Profile & Progress */}
                <div className="lg:w-1/3 space-y-6">
                    <div className="bg-white dark:bg-zinc-900 rounded-2xl border border-zinc-200 dark:border-zinc-800 p-6 shadow-sm">
                        <div className="flex items-center gap-4 mb-6">
                            <div className="w-16 h-16 rounded-full bg-indigo-50 dark:bg-indigo-950/30 flex items-center justify-center text-indigo-600">
                                <GraduationCap size={32} />
                            </div>
                            <div>
                                <h1 className="text-xl font-bold dark:text-white">{student.name}</h1>
                                <p className="text-sm text-zinc-500 font-mono mt-1 pt-1">{student.id}</p>
                            </div>
                        </div>

                        <div className="space-y-3">
                            <div className="flex items-center justify-between text-sm p-3 bg-zinc-50 dark:bg-zinc-800/50 rounded-xl">
                                <span className="text-zinc-500 flex items-center gap-2"><Activity size={16} /> Course ID</span>
                                <span className="font-medium text-zinc-900 dark:text-zinc-300">{student.course_id || 'N/A'}</span>
                            </div>
                            {progress?.previous_attempts !== undefined && (
                                <div className="flex items-center justify-between text-sm p-3 bg-zinc-50 dark:bg-zinc-800/50 rounded-xl">
                                    <span className="text-zinc-500 flex items-center gap-2"><Clock size={16} /> Total Assessments</span>
                                    <span className="font-medium text-zinc-900 dark:text-zinc-300">{progress.previous_attempts}</span>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Competency Scores Map */}
                    {progress?.competency_scores && Object.keys(progress.competency_scores).length > 0 && (
                        <div className="bg-white dark:bg-zinc-900 rounded-2xl border border-zinc-200 dark:border-zinc-800 p-6 shadow-sm">
                            <div className="flex items-center gap-2 mb-4">
                                <TrendingUp size={20} className="text-indigo-600" />
                                <h2 className="font-semibold dark:text-white">Competency Progress</h2>
                            </div>
                            <div className="space-y-4">
                                {Object.entries(progress.competency_scores).map(([comp, score]) => {
                                    const percent = Math.min(100, Math.max(0, (score as number) * 100));
                                    return (
                                        <div key={comp}>
                                            <div className="flex justify-between text-sm mb-1">
                                                <span className="text-zinc-700 dark:text-zinc-300 capitalize">{comp}</span>
                                                <span className="font-medium text-emerald-600 dark:text-emerald-400">{percent.toFixed(0)}%</span>
                                            </div>
                                            <div className="w-full bg-zinc-100 dark:bg-zinc-800 rounded-full h-2">
                                                <div className="bg-emerald-500 h-2 rounded-full" style={{ width: `${percent}%` }}></div>
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        </div>
                    )}
                </div>

                {/* Right: Assessment Sessions */}
                <div className="lg:w-2/3 space-y-6">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <div className="p-2 bg-indigo-50 dark:bg-indigo-950/30 text-indigo-600 rounded-lg">
                                <Clock size={24} />
                            </div>
                            <h2 className="text-xl font-semibold dark:text-white">Assessment Sessions</h2>
                        </div>
                        <span className="text-sm text-zinc-500">{sessions.length} recorded</span>
                    </div>

                    {sessions.length > 0 ? (
                        <div className="bg-white dark:bg-zinc-900 rounded-2xl border border-zinc-200 dark:border-zinc-800 shadow-sm overflow-hidden">
                            <div className="overflow-x-auto">
                                <table className="w-full text-left">
                                    <thead>
                                        <tr className="border-b border-zinc-200 dark:border-zinc-800 bg-zinc-50/50 dark:bg-zinc-800/20">
                                            <th className="px-6 py-4 text-xs font-semibold text-zinc-500 uppercase tracking-wider">Date</th>
                                            <th className="px-6 py-4 text-xs font-semibold text-zinc-500 uppercase tracking-wider">Assignment</th>
                                            <th className="px-6 py-4 text-xs font-semibold text-zinc-500 uppercase tracking-wider">Status</th>
                                            <th className="px-6 py-4 text-xs font-semibold text-zinc-500 uppercase tracking-wider text-right">Action</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800 text-zinc-900 dark:text-zinc-100">
                                        {sessions.map((sess) => (
                                            <tr key={sess.id} className="hover:bg-zinc-50 dark:hover:bg-zinc-800/50 transition-colors group">
                                                <td className="px-6 py-4 text-sm whitespace-nowrap">
                                                    <div className="flex items-center gap-2 text-zinc-600 dark:text-zinc-400">
                                                        <Calendar size={14} />
                                                        {new Date(sess.started_at).toLocaleDateString()}
                                                    </div>
                                                </td>
                                                <td className="px-6 py-4 text-sm font-medium">
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
                                                        className="inline-flex items-center gap-1 text-sm font-medium text-indigo-600 hover:text-indigo-500 dark:text-indigo-400 transition-colors"
                                                    >
                                                        Review <ChevronRight size={16} />
                                                    </Link>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    ) : (
                        <div className="bg-zinc-50 dark:bg-zinc-800/30 rounded-3xl border-2 border-dashed border-zinc-200 dark:border-zinc-800 p-16 text-center">
                            <div className="w-16 h-16 bg-zinc-100 dark:bg-zinc-800 rounded-full flex items-center justify-center mx-auto mb-4">
                                <Clock size={24} className="text-zinc-400" />
                            </div>
                            <h3 className="text-lg font-semibold dark:text-white">No Sessions Yet</h3>
                            <p className="text-zinc-500 max-w-sm mx-auto mt-2">This student hasn't participated in any recorded assessments.</p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
