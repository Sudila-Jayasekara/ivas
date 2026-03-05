'use client';

import { useParams, useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import {
    ArrowLeft,
    Sparkles,
    BookOpen,
    ListChecks,
    Plus,
    Trash2,
    RefreshCw,
    CheckCircle2,
    AlertCircle
} from 'lucide-react';
import Link from 'next/link';

export default function AssignmentDetailsPage() {
    const { id } = useParams();
    const [assignment, setAssignment] = useState<any>(null);
    const [criteria, setCriteria] = useState<any[]>([]);
    const [questions, setQuestions] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [generating, setGenerating] = useState(false);
    const [generatingQuestions, setGeneratingQuestions] = useState(false);
    const [assignmentText, setAssignmentText] = useState('');

    const fetchData = async () => {
        setLoading(true);
        try {
            const a = await api.getAssignment(id as string);
            setAssignment(a);
            setAssignmentText(a.description || '');

            const c = await api.getCriteria(id as string);
            setCriteria(c);

            const q = await api.getQuestions(id as string);
            setQuestions(q);
        } catch (error) {
            console.error('Failed to fetch assignment data', error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
    }, [id]);

    const handleGenerateCriteria = async () => {
        if (!assignmentText) return;
        setGenerating(true);
        try {
            await api.generateCriteria(id as string, {
                assignment_text: assignmentText,
                num_criteria: 5
            });
            await fetchData();
        } catch (error) {
            alert('Failed to generate criteria');
        } finally {
            setGenerating(false);
        }
    };

    const handleEditCriteria = async (item: any) => {
        const newLabel = prompt('Enter new level label:', item.level_label);
        if (!newLabel || newLabel === item.level_label) return;

        try {
            await api.updateCriteria(item.id, { level_label: newLabel });
            await fetchData();
        } catch (error) {
            console.error('Failed to update criteria', error);
            alert('Failed to update criteria');
        }
    };

    const handleGenerateQuestions = async () => {
        if (!assignmentText) return;
        setGeneratingQuestions(true);
        try {
            await api.generateQuestions(id as string, {
                assignment_text: assignmentText,
                num_questions: 2
            });
            await fetchData();
        } catch (error) {
            alert('Failed to generate questions');
        } finally {
            setGeneratingQuestions(false);
        }
    };

    const router = useRouter();
    const [triggering, setTriggering] = useState(false);

    const handleStartViva = async () => {
        setTriggering(true);
        try {
            const resp = await api.triggerAssessment("STU001", id as string);
            // Assuming resp contains session_id
            if (resp.session_id) {
                router.push(`/viva/${resp.session_id}`);
            } else {
                alert("Assessment triggered. Please check sessions.");
            }
        } catch (error) {
            console.error('Failed to start viva', error);
            alert('Failed to start viva assessment. Make sure backend is running.');
        } finally {
            setTriggering(false);
        }
    };

    if (loading && !assignment) {
        return (
            <div className="flex items-center justify-center min-h-[60vh]">
                <RefreshCw className="animate-spin text-indigo-600" size={32} />
            </div>
        );
    }

    return (
        <div className="space-y-8 pb-20">
            <Link href="/assignments" className="inline-flex items-center gap-2 text-zinc-500 hover:text-zinc-900 dark:hover:text-white transition-colors">
                <ArrowLeft size={18} />
                Back to Assignments
            </Link>

            <div className="flex flex-col lg:flex-row gap-8">
                {/* Left: Assignment Info */}
                <div className="lg:w-1/3 space-y-6">
                    <div className="bg-white dark:bg-zinc-900 rounded-2xl border border-zinc-200 dark:border-zinc-800 p-6 shadow-sm">
                        <div className="flex items-center gap-3 mb-4">
                            <div className="p-2 bg-indigo-50 dark:bg-indigo-950/30 text-indigo-600 rounded-lg">
                                <BookOpen size={24} />
                            </div>
                            <h1 className="text-2xl font-bold dark:text-white">{assignment?.title}</h1>
                        </div>

                        <div className="space-y-4">
                            <div>
                                <label className="text-xs font-semibold text-zinc-400 uppercase tracking-widest">Description</label>
                                <textarea
                                    className="w-full mt-2 p-3 bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-200 dark:border-zinc-800 rounded-xl text-sm min-h-[200px] focus:outline-none focus:ring-2 focus:ring-indigo-500 dark:text-white"
                                    value={assignmentText}
                                    onChange={(e) => setAssignmentText(e.target.value)}
                                />
                            </div>

                            <div className="flex items-center justify-between text-sm">
                                <span className="text-zinc-500">Course ID:</span>
                                <span className="font-mono text-zinc-900 dark:text-zinc-300">{assignment?.course_id}</span>
                            </div>
                        </div>
                    </div>

                    <button
                        onClick={handleStartViva}
                        disabled={triggering}
                        className="w-full flex items-center justify-center gap-3 p-4 bg-emerald-600 hover:bg-emerald-700 disabled:bg-emerald-400 text-white rounded-2xl font-semibold shadow-lg shadow-emerald-200 dark:shadow-none transition-all mb-4"
                    >
                        {triggering ? <RefreshCw className="animate-spin" size={20} /> : <CheckCircle2 size={20} />}
                        {triggering ? 'Starting Viva...' : 'Start Student Viva'}
                    </button>

                    <button
                        onClick={handleGenerateCriteria}
                        disabled={generating}
                        className="w-full flex items-center justify-center gap-3 p-4 bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-400 text-white rounded-2xl font-semibold shadow-lg shadow-indigo-200 dark:shadow-none transition-all"
                    >
                        {generating ? <RefreshCw className="animate-spin" size={20} /> : <Sparkles size={20} />}
                        {generating ? 'Contextualizing Criteria...' : 'Generate Grading Criteria'}
                    </button>

                    <button
                        onClick={handleGenerateQuestions}
                        disabled={generatingQuestions || criteria.length === 0}
                        className="w-full flex items-center justify-center gap-3 p-4 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white rounded-2xl font-semibold shadow-lg shadow-blue-200 dark:shadow-none transition-all mt-4"
                    >
                        {generatingQuestions ? <RefreshCw className="animate-spin" size={20} /> : <ListChecks size={20} />}
                        {generatingQuestions ? 'Generating Questions...' : 'Generate Questions'}
                    </button>
                </div>

                {/* Right: Grading Criteria & Questions */}
                <div className="lg:w-2/3 space-y-6">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <div className="p-2 bg-emerald-50 dark:bg-emerald-950/30 text-emerald-600 rounded-lg">
                                <ListChecks size={24} />
                            </div>
                            <h2 className="text-xl font-semibold dark:text-white">Grading Criteria</h2>
                        </div>
                        <span className="text-sm text-zinc-500">{criteria.length} items defined</span>
                    </div>

                    {criteria.length > 0 ? (
                        <div className="grid grid-cols-1 gap-4">
                            {criteria.map((item) => (
                                <div key={item.id} className="bg-white dark:bg-zinc-900 rounded-2xl border border-zinc-200 dark:border-zinc-800 p-6 shadow-sm hover:border-indigo-300 dark:hover:border-zinc-700 transition-all group">
                                    <div className="flex items-start justify-between mb-4">
                                        <div>
                                            <h3 className="font-bold text-lg text-zinc-900 dark:text-white">{item.competency}</h3>
                                            <div className="flex items-center gap-2 mt-1">
                                                <span className="px-2 py-0.5 rounded-full bg-indigo-50 dark:bg-indigo-950/30 text-[10px] font-bold text-indigo-700 dark:text-indigo-400 uppercase tracking-wider">
                                                    Level {item.difficulty_level}: {item.level_label}
                                                </span>
                                                <span className="px-2 py-0.5 rounded-full bg-zinc-100 dark:bg-zinc-800 text-[10px] font-bold text-zinc-600 dark:text-zinc-400 uppercase tracking-wider">
                                                    {item.programming_language}
                                                </span>
                                            </div>
                                        </div>
                                        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                            <button
                                                onClick={() => handleEditCriteria(item)}
                                                className="p-2 text-zinc-400 hover:text-indigo-500 transition-colors"
                                                title="Edit Label"
                                            >
                                                <AlertCircle size={18} />
                                            </button>
                                            <button className="p-2 text-zinc-400 hover:text-red-500 transition-colors" title="Delete">
                                                <Trash2 size={18} />
                                            </button>
                                        </div>
                                    </div>

                                    <p className="text-sm text-zinc-600 dark:text-zinc-400 mb-4">{item.level_description}</p>

                                    <div className="bg-zinc-50 dark:bg-zinc-800/50 rounded-xl p-4 border border-zinc-100 dark:border-zinc-800">
                                        <p className="text-xs font-bold text-zinc-400 uppercase tracking-widest mb-2">Marking Rubric</p>
                                        <p className="text-sm text-zinc-700 dark:text-zinc-300 italic">{item.marking_criteria}</p>
                                    </div>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="bg-zinc-50 dark:bg-zinc-800/30 rounded-3xl border-2 border-dashed border-zinc-200 dark:border-zinc-800 p-20 text-center">
                            <div className="w-16 h-16 bg-zinc-100 dark:bg-zinc-800 rounded-full flex items-center justify-center mx-auto mb-4">
                                <Sparkles size={24} className="text-zinc-400" />
                            </div>
                            <h3 className="text-lg font-semibold dark:text-white">No Criteria Yet</h3>
                            <p className="text-zinc-500 max-w-xs mx-auto mt-2">Generate grading criteria based on your assignment text to start the assessment process.</p>
                        </div>
                    )}

                    {/* Questions Section */}
                    {criteria.length > 0 && (
                        <div className="mt-12">
                            <div className="flex items-center justify-between border-t border-zinc-200 dark:border-zinc-800 pt-8">
                                <div className="flex items-center gap-3">
                                    <div className="p-2 bg-blue-50 dark:bg-blue-950/30 text-blue-600 rounded-lg">
                                        <BookOpen size={24} />
                                    </div>
                                    <h2 className="text-xl font-semibold dark:text-white">Generated Questions</h2>
                                </div>
                                <span className="text-sm text-zinc-500">{questions.length} questions</span>
                            </div>

                            {questions.length > 0 ? (
                                <div className="grid grid-cols-1 gap-4 mt-6">
                                    {questions.map((q) => (
                                        <div key={q.id} className="bg-white dark:bg-zinc-900 rounded-2xl border border-zinc-200 dark:border-zinc-800 p-6 shadow-sm">
                                            <div className="flex items-start justify-between mb-2">
                                                <p className="font-medium text-zinc-900 dark:text-white">{q.text}</p>
                                                <span className="px-2 py-0.5 rounded-full bg-blue-50 dark:bg-blue-950/30 text-[10px] font-bold text-blue-700 dark:text-blue-400 uppercase tracking-wider ml-4 shrink-0">
                                                    Diff: {q.difficulty}
                                                </span>
                                            </div>
                                            <div className="bg-zinc-50 dark:bg-zinc-800/50 rounded-xl p-4 border border-zinc-100 dark:border-zinc-800 mt-4">
                                                <p className="text-xs font-bold text-zinc-400 uppercase tracking-widest mb-2">Expected Answer</p>
                                                <p className="text-sm text-zinc-700 dark:text-zinc-300 italic">{q.expected_answer}</p>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <div className="bg-zinc-50 dark:bg-zinc-800/30 rounded-3xl border-2 border-dashed border-zinc-200 dark:border-zinc-800 p-12 text-center mt-6">
                                    <p className="text-zinc-500 max-w-xs mx-auto">No questions generated yet. Generate them based on the criteria.</p>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
