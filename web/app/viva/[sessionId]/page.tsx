'use client';

import { useParams, useRouter } from 'next/navigation';
import { useEffect, useState, useRef } from 'react';
import { api } from '@/lib/api';
import {
    Send,
    User,
    Bot,
    Loader2,
    CheckCircle,
    AlertTriangle,
    Code,
    ArrowLeft
} from 'lucide-react';
import Link from 'next/link';

interface Message {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    timestamp: Date;
}

export default function VivaSessionPage() {
    const { sessionId } = useParams();
    const router = useRouter();
    const [session, setSession] = useState<any>(null);
    const [messages, setMessages] = useState<Message[]>([]);
    const [inputValue, setInputValue] = useState('');
    const [loading, setLoading] = useState(true);
    const [sending, setSending] = useState(false);
    const scrollRef = useRef<HTMLDivElement>(null);

    const fetchSession = async () => {
        try {
            const data = await api.getSession(sessionId as string);
            setSession(data);

            // Try to fetch transcript to rehydrate messages
            try {
                const t = await api.getTranscript(sessionId as string);
                const transcriptData = Array.isArray(t) ? t : (t.data || []);
                if (transcriptData.length > 0) {
                    const hydrated = transcriptData.map((item: any, i: number) => ({
                        id: item.id || `t-${i}`,
                        role: item.role === 'assistant' || item.role === 'system' ? 'assistant' : 'user',
                        content: item.content || item.text || JSON.stringify(item),
                        timestamp: new Date(item.timestamp || Date.now())
                    }));
                    setMessages(hydrated);
                }
            } catch (e) {
                console.warn('Transcript not loaded', e);
            }
        } catch (error) {
            console.error('Failed to fetch session', error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchSession();
    }, [sessionId]);

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [messages]);

    const handleSend = async () => {
        if (!inputValue.trim() || sending) return;

        const userMsg: Message = {
            id: Date.now().toString(),
            role: 'user',
            content: inputValue,
            timestamp: new Date()
        };

        setMessages(prev => [...prev, userMsg]);
        setInputValue('');
        setSending(true);

        try {
            // Assuming we need current_question_id from session state
            // This part depends on backend's response format for session
            await api.submitResponse(sessionId as string, {
                question_instance_id: session?.current_question_id || 'manual',
                response_text: inputValue
            });

            // Refresh session to get next question or updated state
            const updatedSession = await api.getSession(sessionId as string);
            setSession(updatedSession);

            // Mocking assistant response for now (usually comes from transcript or session state)
            const assistantMsg: Message = {
                id: (Date.now() + 1).toString(),
                role: 'assistant',
                content: "I've received your response. Let's move to the next part of the assessment.",
                timestamp: new Date()
            };
            setMessages(prev => [...prev, assistantMsg]);

            if (updatedSession.status === 'completed') {
                alert('Viva completed successfully!');
                router.push('/');
            }
        } catch (error) {
            console.error('Failed to submit response', error);
        } finally {
            setSending(false);
        }
    };

    const handleAbandon = async () => {
        if (!confirm('Are you sure you want to abandon this session?')) return;
        try {
            await api.abandonSession(sessionId as string);
            const updated = await api.getSession(sessionId as string);
            setSession(updated);
        } catch (error) {
            console.error('Failed to abandon session', error);
        }
    };

    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center min-h-[70vh] gap-4">
                <Loader2 className="animate-spin text-indigo-600" size={48} />
                <p className="text-zinc-500 font-medium animate-pulse">Initializing Assessment Session...</p>
            </div>
        );
    }

    return (
        <div className="flex flex-col h-[calc(100vh-160px)] max-w-4xl mx-auto">
            {/* Session Header */}
            <div className="flex items-center justify-between mb-6 bg-white dark:bg-zinc-900 p-4 rounded-2xl border border-zinc-200 dark:border-zinc-800 shadow-sm">
                <div className="flex items-center gap-4">
                    <div className="w-10 h-10 rounded-full bg-indigo-50 dark:bg-indigo-950/30 flex items-center justify-center text-indigo-600">
                        <Code size={20} />
                    </div>
                    <div>
                        <h1 className="font-bold text-zinc-900 dark:text-white">Active Viva Session</h1>
                        <p className="text-xs text-zinc-500 font-mono">ID: {sessionId}</p>
                    </div>
                </div>
                <div className="flex items-center gap-4">
                    {session?.status === 'active' ? (
                        <>
                            <span className="flex h-3 w-3 rounded-full bg-emerald-500 animate-pulse"></span>
                            <span className="text-xs font-bold text-emerald-600 uppercase tracking-widest">Live</span>
                            <button onClick={handleAbandon} className="text-xs font-bold text-red-600 hover:text-red-700 uppercase tracking-widest px-2 py-1 bg-red-50 dark:bg-red-950/30 rounded-lg transition-colors">Abandon</button>
                        </>
                    ) : (
                        <>
                            <span className="flex h-3 w-3 rounded-full bg-zinc-400"></span>
                            <span className="text-xs font-bold text-zinc-500 uppercase tracking-widest">{session?.status}</span>
                        </>
                    )}
                </div>
            </div>

            {/* Chat Area */}
            <div
                ref={scrollRef}
                className="flex-1 overflow-y-auto space-y-6 px-4 py-8 mb-6 scrollbar-hide bg-zinc-50/50 dark:bg-zinc-950/20 rounded-3xl border border-zinc-100 dark:border-zinc-900"
            >
                {messages.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full text-center space-y-4">
                        <div className="p-4 bg-indigo-50 dark:bg-indigo-950/30 rounded-full text-indigo-600">
                            <Bot size={32} />
                        </div>
                        <div className="max-w-xs">
                            <h3 className="font-bold text-zinc-900 dark:text-white">Start your viva</h3>
                            <p className="text-sm text-zinc-500 mt-1">Submit your first response to begin the interview.</p>
                        </div>
                    </div>
                ) : (
                    messages.map((msg) => (
                        <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                            <div className={`flex gap-3 max-w-[80%] ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
                                <div className={`
                  w-8 h-8 rounded-lg flex items-center justify-center shrink-0
                  ${msg.role === 'user' ? 'bg-indigo-600 text-white' : 'bg-zinc-200 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400'}
                `}>
                                    {msg.role === 'user' ? <User size={16} /> : <Bot size={16} />}
                                </div>
                                <div className={`
                  p-4 rounded-2xl text-sm leading-relaxed shadow-sm
                  ${msg.role === 'user'
                                        ? 'bg-indigo-600 text-white rounded-tr-none'
                                        : 'bg-white dark:bg-zinc-900 text-zinc-800 dark:text-zinc-200 border border-zinc-200 dark:border-zinc-800 rounded-tl-none'}
                `}>
                                    {msg.content}
                                    <p className={`text-[10px] mt-2 opacity-60 text-right ${msg.role === 'user' ? 'text-white' : 'text-zinc-500'}`}>
                                        {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                    </p>
                                </div>
                            </div>
                        </div>
                    ))
                )}
                {sending && (
                    <div className="flex justify-start">
                        <div className="flex gap-3 bg-white dark:bg-zinc-900 p-3 rounded-2xl border border-zinc-200 dark:border-zinc-800">
                            <div className="flex gap-1 items-center">
                                <span className="w-1.5 h-1.5 bg-zinc-300 rounded-full animate-bounce"></span>
                                <span className="w-1.5 h-1.5 bg-zinc-300 rounded-full animate-bounce [animation-delay:0.2s]"></span>
                                <span className="w-1.5 h-1.5 bg-zinc-300 rounded-full animate-bounce [animation-delay:0.4s]"></span>
                            </div>
                        </div>
                    </div>
                )}
            </div>

            {/* Input Area */}
            <div className="relative">
                <div className="absolute -top-12 left-0 right-0 flex justify-center pointer-events-none">
                    <div className="bg-white dark:bg-zinc-900 px-4 py-1 rounded-full border border-zinc-200 dark:border-zinc-800 shadow-sm text-[10px] font-bold text-zinc-400 uppercase tracking-widest pointer-events-auto">
                        Code interaction enabled
                    </div>
                </div>

                <div className="bg-white dark:bg-zinc-900 p-2 rounded-2xl border-2 border-zinc-200 dark:border-zinc-800 focus-within:border-indigo-500 shadow-lg transition-all">
                    <div className="flex items-end gap-2 px-2">
                        <textarea
                            rows={2}
                            disabled={session?.status !== 'active' || sending}
                            className="flex-1 py-3 bg-transparent border-none focus:ring-0 text-zinc-900 dark:text-white resize-none text-sm placeholder:text-zinc-400 disabled:opacity-50"
                            placeholder={session?.status === 'active' ? "Type your response here..." : "Session ended. Input disabled."}
                            value={inputValue}
                            onChange={(e) => setInputValue(e.target.value)}
                            onKeyDown={(e) => {
                                if (e.key === 'Enter' && !e.shiftKey) {
                                    e.preventDefault();
                                    handleSend();
                                }
                            }}
                        />
                        <button
                            onClick={handleSend}
                            disabled={!inputValue.trim() || sending || session?.status !== 'active'}
                            className="mb-1.5 p-2 bg-indigo-600 hover:bg-indigo-700 disabled:bg-zinc-300 text-white rounded-xl transition-all active:scale-95"
                        >
                            <Send size={20} />
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
