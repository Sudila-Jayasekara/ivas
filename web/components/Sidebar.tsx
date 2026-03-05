'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
    LayoutDashboard,
    BookOpen,
    Settings,
    MessageSquare,
    ShieldCheck,
    Users,
    Clock,
    Menu,
    X
} from 'lucide-react';
import { useState } from 'react';

const navItems = [
    { name: 'Dashboard', href: '/', icon: LayoutDashboard },
    { name: 'Assignments', href: '/assignments', icon: BookOpen },
    { name: 'Students', href: '/students', icon: Users },
    { name: 'Sessions', href: '/sessions', icon: Clock },
];

export default function Sidebar() {
    const pathname = usePathname();
    const [isOpen, setIsOpen] = useState(true);

    return (
        <>
            {/* Mobile Toggle */}
            <button
                className="fixed top-4 left-4 z-50 p-2 bg-white dark:bg-zinc-900 rounded-md shadow-md lg:hidden"
                onClick={() => setIsOpen(!isOpen)}
            >
                {isOpen ? <X size={20} /> : <Menu size={20} />}
            </button>

            {/* Sidebar */}
            <aside className={`
        fixed top-0 left-0 z-40 h-full transition-transform duration-300 ease-in-out
        ${isOpen ? 'translate-x-0' : '-translate-x-full'}
        w-64 bg-white dark:bg-zinc-950 border-r border-zinc-200 dark:border-zinc-800
        lg:translate-x-0
      `}>
                <div className="flex flex-col h-full px-4 py-6">
                    <div className="flex items-center gap-2 mb-10 px-2">
                        <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center">
                            <span className="text-white font-bold">i</span>
                        </div>
                        <h1 className="text-xl font-bold tracking-tight">IVAS</h1>
                    </div>

                    <nav className="flex-1 space-y-1">
                        {navItems.map((item) => {
                            const isActive = pathname === item.href;
                            return (
                                <Link
                                    key={item.name}
                                    href={item.href}
                                    className={`
                    flex items-center gap-3 px-3 py-2 rounded-lg transition-colors
                    ${isActive
                                            ? 'bg-indigo-50 text-indigo-700 dark:bg-indigo-950/30 dark:text-indigo-400'
                                            : 'text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-900'}
                  `}
                                >
                                    <item.icon size={20} />
                                    <span className="font-medium">{item.name}</span>
                                </Link>
                            );
                        })}
                    </nav>

                    <div className="mt-auto pt-4 border-t border-zinc-200 dark:border-zinc-800">
                        <Link
                            href="/settings"
                            className={`
                flex items-center gap-3 px-3 py-2 rounded-lg transition-colors
                ${pathname === '/settings'
                                    ? 'bg-zinc-100 text-zinc-900 dark:bg-zinc-900 dark:text-zinc-100'
                                    : 'text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-900'}
              `}
                        >
                            <Settings size={20} />
                            <span className="font-medium">Settings</span>
                        </Link>
                    </div>
                </div>
            </aside>

            {/* Overlay for mobile */}
            {isOpen && (
                <div
                    className="fixed inset-0 z-30 bg-black/20 backdrop-blur-sm lg:hidden"
                    onClick={() => setIsOpen(false)}
                />
            )}
        </>
    );
}
