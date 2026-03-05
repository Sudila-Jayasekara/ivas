'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import {
    Search,
    Filter,
    MoreVertical,
    ExternalLink,
    Plus,
    ArrowUpDown
} from 'lucide-react';
import Link from 'next/link';

export default function AssignmentsPage() {
    const [assignments, setAssignments] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState('');

    useEffect(() => {
        const fetchAssignments = async () => {
            try {
                const data = await api.getAssignments();
                setAssignments(data);
            } catch (error) {
                console.error('Failed to fetch assignments', error);
            } finally {
                setLoading(false);
            }
        };
        fetchAssignments();
    }, []);

    const filteredAssignments = assignments.filter(a =>
        a.title?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        a.description?.toLowerCase().includes(searchQuery.toLowerCase())
    );

    return (
        <div className="space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-bold text-zinc-900 dark:text-white">Assignments</h1>
                    <p className="text-zinc-500 dark:text-zinc-400 mt-1">Manage all course assignments and grading criteria.</p>
                </div>
                <button className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg font-medium transition-colors shadow-sm self-start sm:self-auto">
                    <Plus size={18} />
                    <span>New Assignment</span>
                </button>
            </div>

            {/* Filters & Search */}
            <div className="flex flex-col md:flex-row gap-4">
                <div className="relative flex-1">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" size={18} />
                    <input
                        type="text"
                        placeholder="Search assignments..."
                        className="w-full pl-10 pr-4 py-2 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 dark:text-white"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                    />
                </div>
                <button className="inline-flex items-center gap-2 border border-zinc-200 dark:border-zinc-800 px-4 py-2 rounded-lg bg-white dark:bg-zinc-900 text-zinc-700 dark:text-zinc-300 hover:bg-zinc-50 dark:hover:bg-zinc-800 transition-colors">
                    <Filter size={18} />
                    <span>Filters</span>
                </button>
                <button className="inline-flex items-center gap-2 border border-zinc-200 dark:border-zinc-800 px-4 py-2 rounded-lg bg-white dark:bg-zinc-900 text-zinc-700 dark:text-zinc-300 hover:bg-zinc-50 dark:hover:bg-zinc-800 transition-colors">
                    <ArrowUpDown size={18} />
                    <span>Sort</span>
                </button>
            </div>

            {/* Assignments Table */}
            <div className="bg-white dark:bg-zinc-900 rounded-2xl border border-zinc-200 dark:border-zinc-800 shadow-sm overflow-hidden">
                {loading ? (
                    <div className="p-12 text-center">
                        <div className="w-8 h-8 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
                        <p className="text-zinc-500">Loading assignments...</p>
                    </div>
                ) : filteredAssignments.length > 0 ? (
                    <div className="overflow-x-auto">
                        <table className="w-full text-left">
                            <thead>
                                <tr className="border-b border-zinc-200 dark:border-zinc-800 bg-zinc-50/50 dark:bg-zinc-800/20">
                                    <th className="px-6 py-4 text-xs font-semibold text-zinc-500 uppercase tracking-wider">Title</th>
                                    <th className="px-6 py-4 text-xs font-semibold text-zinc-500 uppercase tracking-wider">Course ID</th>
                                    <th className="px-6 py-4 text-xs font-semibold text-zinc-500 uppercase tracking-wider">Instructor ID</th>
                                    <th className="px-6 py-4 text-xs font-semibold text-zinc-500 uppercase tracking-wider">Status</th>
                                    <th className="px-6 py-4 text-xs font-semibold text-zinc-500 uppercase tracking-wider"></th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800 text-zinc-900 dark:text-zinc-100">
                                {filteredAssignments.map((assignment) => (
                                    <tr key={assignment.assignment_id} className="hover:bg-zinc-50 dark:hover:bg-zinc-800/50 transition-colors group">
                                        <td className="px-6 py-4">
                                            <div className="flex flex-col">
                                                <span className="font-medium group-hover:text-indigo-600 transition-colors">
                                                    {assignment.title}
                                                </span>
                                                <span className="text-xs text-zinc-500 mt-0.5 line-clamp-1">
                                                    {assignment.description}
                                                </span>
                                            </div>
                                        </td>
                                        <td className="px-6 py-4 text-sm font-mono text-zinc-500">{assignment.course_id}</td>
                                        <td className="px-6 py-4 text-sm font-mono text-zinc-500">{assignment.instructor_id}</td>
                                        <td className="px-6 py-4">
                                            <span className="inline-flex items-center rounded-full bg-emerald-50 dark:bg-emerald-950/30 px-2 py-1 text-xs font-medium text-emerald-700 dark:text-emerald-400">
                                                Active
                                            </span>
                                        </td>
                                        <td className="px-6 py-4 text-right">
                                            <div className="flex items-center justify-end gap-2">
                                                <Link
                                                    href={`/assignments/${assignment.assignment_id}`}
                                                    className="p-2 text-zinc-400 hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors"
                                                >
                                                    <ExternalLink size={18} />
                                                </Link>
                                                <button className="p-2 text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200 transition-colors">
                                                    <MoreVertical size={18} />
                                                </button>
                                            </div>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                ) : (
                    <div className="p-12 text-center">
                        <p className="text-zinc-500">No assignments found matching your criteria.</p>
                    </div>
                )}
            </div>
        </div>
    );
}
