'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import {
  Users,
  BookOpen,
  CheckCircle2,
  Clock,
  ArrowRight,
  Plus
} from 'lucide-react';
import Link from 'next/link';

export default function Dashboard() {
  const [stats, setStats] = useState([
    { name: 'Total Students', value: '0', icon: Users, color: 'text-blue-600', bg: 'bg-blue-50' },
    { name: 'Active Assignments', value: '0', icon: BookOpen, color: 'text-indigo-600', bg: 'bg-indigo-50' },
    { name: 'Completed Vivas', value: '0', icon: CheckCircle2, color: 'text-emerald-600', bg: 'bg-emerald-50' },
    { name: 'Pending Reviews', value: '0', icon: Clock, color: 'text-amber-600', bg: 'bg-amber-50' },
  ]);

  const [recentAssignments, setRecentAssignments] = useState<any[]>([]);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const assignments = await api.getAssignments();
        setRecentAssignments(assignments.slice(0, 3));

        // Mocking stats for now based on assignments
        setStats([
          { name: 'Total Students', value: '124', icon: Users, color: 'text-blue-600', bg: 'bg-blue-50 dark:bg-blue-950/30' },
          { name: 'Active Assignments', value: assignments.length.toString(), icon: BookOpen, color: 'text-indigo-600', bg: 'bg-indigo-50 dark:bg-indigo-950/30' },
          { name: 'Completed Vivas', value: '89', icon: CheckCircle2, color: 'text-emerald-600', bg: 'bg-emerald-50 dark:bg-emerald-950/30' },
          { name: 'Pending Reviews', value: '12', icon: Clock, color: 'text-amber-600', bg: 'bg-amber-50 dark:bg-amber-950/30' },
        ]);
      } catch (error) {
        console.error('Failed to fetch dashboard data', error);
      }
    };
    fetchData();
  }, []);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-zinc-900 dark:text-white">Dashboard</h1>
        <p className="text-zinc-500 dark:text-zinc-400 mt-1">Welcome back, Professor.</p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {stats.map((stat) => (
          <div key={stat.name} className="p-6 bg-white dark:bg-zinc-900 rounded-2xl border border-zinc-200 dark:border-zinc-800 shadow-sm transition-all hover:shadow-md">
            <div className={`w-12 h-12 ${stat.bg} ${stat.color} rounded-xl flex items-center justify-center mb-4`}>
              <stat.icon size={24} />
            </div>
            <p className="text-sm font-medium text-zinc-500 dark:text-zinc-400">{stat.name}</p>
            <p className="text-2xl font-bold text-zinc-900 dark:text-white mt-1">{stat.value}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Recent Assignments */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold text-zinc-900 dark:text-white">Recent Assignments</h2>
            <Link href="/assignments" className="text-sm font-medium text-indigo-600 hover:text-indigo-500 flex items-center gap-1">
              View all <ArrowRight size={16} />
            </Link>
          </div>

          <div className="bg-white dark:bg-zinc-900 rounded-2xl border border-zinc-200 dark:border-zinc-800 overflow-hidden shadow-sm">
            {recentAssignments.length > 0 ? (
              <div className="divide-y divide-zinc-200 dark:divide-zinc-800">
                {recentAssignments.map((assignment) => (
                  <div key={assignment.assignment_id} className="p-6 hover:bg-zinc-50 dark:hover:bg-zinc-800/50 transition-colors cursor-pointer group">
                    <div className="flex items-center justify-between">
                      <div>
                        <h3 className="font-semibold text-zinc-900 dark:text-white group-hover:text-indigo-600 transition-colors">
                          {assignment.title}
                        </h3>
                        <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1 line-clamp-1">
                          {assignment.description}
                        </p>
                      </div>
                      <div className="text-right">
                        <span className="inline-flex items-center rounded-full bg-indigo-50 dark:bg-indigo-950/30 px-2 py-1 text-xs font-medium text-indigo-700 dark:text-indigo-400 ring-1 ring-inset ring-indigo-700/10">
                          Active
                        </span>
                        <p className="text-xs text-zinc-400 mt-2">ID: {assignment.assignment_id}</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-12 text-center">
                <p className="text-zinc-500">No assignments found.</p>
              </div>
            )}
          </div>
        </div>

        {/* Quick Actions */}
        <div className="space-y-4">
          <h2 className="text-xl font-semibold text-zinc-900 dark:text-white">Quick Actions</h2>
          <div className="grid grid-cols-1 gap-4">
            <button className="flex items-center gap-4 p-4 text-left bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl shadow-lg shadow-indigo-200 dark:shadow-none transition-all scale-100 hover:scale-[1.02] active:scale-[0.98]">
              <div className="bg-white/20 p-2 rounded-lg">
                <Plus size={20} />
              </div>
              <div>
                <p className="font-semibold">New Assignment</p>
                <p className="text-xs text-indigo-100 italic">Create and set criteria</p>
              </div>
            </button>

            <button className="flex items-center gap-4 p-4 text-left bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 hover:border-indigo-300 dark:hover:border-indigo-900 rounded-xl shadow-sm transition-all scale-100 hover:scale-[1.02] active:scale-[0.98]">
              <div className="bg-emerald-50 dark:bg-emerald-950/30 p-2 rounded-lg text-emerald-600">
                <CheckCircle2 size={20} />
              </div>
              <div>
                <p className="font-semibold dark:text-white">Run Assessment</p>
                <p className="text-xs text-zinc-500 italic">Trigger student viva</p>
              </div>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
