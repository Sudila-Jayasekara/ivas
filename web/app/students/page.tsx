'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import {
    Users,
    Search,
    ChevronRight,
    GraduationCap,
    TrendingUp,
    Clock
} from 'lucide-react';
import Link from 'next/link';

export default function StudentsPage() {
    const [students, setStudents] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState('');

    useEffect(() => {
        const fetchStudents = async () => {
            try {
                const data = await api.getStudents();
                setStudents(data);
            } catch (error) {
                console.error('Failed to fetch students', error);
            } finally {
                setLoading(false);
            }
        };
        fetchStudents();
    }, []);

    const filteredStudents = students.filter(s =>
        s.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        s.id?.toLowerCase().includes(searchQuery.toLowerCase())
    );

    return (
        <div className="space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-bold text-zinc-900 dark:text-white">Students</h1>
                    <p className="text-zinc-500 dark:text-zinc-400 mt-1">Monitor student progress and assessment history.</p>
                </div>
            </div>

            {/* Search */}
            <div className="relative max-w-md">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" size={18} />
                <input
                    type="text"
                    placeholder="Search students..."
                    className="w-full pl-10 pr-4 py-2 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 dark:text-white"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                />
            </div>

            {/* Students Table */}
            <div className="bg-white dark:bg-zinc-900 rounded-2xl border border-zinc-200 dark:border-zinc-800 shadow-sm overflow-hidden">
                {loading ? (
                    <div className="p-12 text-center">
                        <div className="w-8 h-8 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
                        <p className="text-zinc-500">Loading students...</p>
                    </div>
                ) : filteredStudents.length > 0 ? (
                    <div className="overflow-x-auto">
                        <table className="w-full text-left">
                            <thead>
                                <tr className="border-b border-zinc-200 dark:border-zinc-800 bg-zinc-50/50 dark:bg-zinc-800/20">
                                    <th className="px-6 py-4 text-xs font-semibold text-zinc-500 uppercase tracking-wider">Student</th>
                                    <th className="px-6 py-4 text-xs font-semibold text-zinc-500 uppercase tracking-wider">Course ID</th>
                                    <th className="px-6 py-4 text-xs font-semibold text-zinc-500 uppercase tracking-wider">ID</th>
                                    <th className="px-6 py-4 text-xs font-semibold text-zinc-500 uppercase tracking-wider text-right">Details</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800 text-zinc-900 dark:text-zinc-100">
                                {filteredStudents.map((student) => (
                                    <tr key={student.id} className="hover:bg-zinc-50 dark:hover:bg-zinc-800/50 transition-colors group">
                                        <td className="px-6 py-4">
                                            <div className="flex items-center gap-3">
                                                <div className="w-10 h-10 rounded-full bg-indigo-50 dark:bg-indigo-950/30 flex items-center justify-center text-indigo-600">
                                                    <Users size={20} />
                                                </div>
                                                <span className="font-medium group-hover:text-indigo-600 transition-colors">
                                                    {student.name}
                                                </span>
                                            </div>
                                        </td>
                                        <td className="px-6 py-4 text-sm font-mono text-zinc-500">
                                            {student.course_id || 'N/A'}
                                        </td>
                                        <td className="px-6 py-4 text-sm font-mono text-zinc-400">
                                            {student.id}
                                        </td>
                                        <td className="px-6 py-4 text-right">
                                            <Link
                                                href={`/students/${student.id}`}
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
                        <p className="text-zinc-500">No students found matching your search.</p>
                    </div>
                )}
            </div>
        </div>
    );
}
