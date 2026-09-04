/**
 * React TopHeader Component
 * Premium clinical command bar with live clock, quick actions, and theme switch
 */

(function() {
    'use strict';
    const { useState, useEffect } = window.React;
    const html = window.html;

    function TopHeader({ user, doctorSpecialization, isDemo }) {
        const [time, setTime] = useState(new Date());
        const themeMgr = window.CmsTheme || window.ImhotepTheme;
        const [isDark, setIsDark] = useState(themeMgr ? themeMgr.isDark() : false);
        const [quickActionsOpen, setQuickActionsOpen] = useState(false);

        useEffect(() => {
            const timer = setInterval(() => setTime(new Date()), 1000);
            return () => clearInterval(timer);
        }, []);

        const handleThemeToggle = () => {
            const tm = window.CmsTheme || window.ImhotepTheme;
            if (tm) {
                const nextDark = tm.toggle();
                setIsDark(nextDark);
            }
        };

        const formattedTime = time.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        const formattedDate = time.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' });

        return html`
            <header className="sticky top-0 z-40 w-full backdrop-blur-xl bg-white/80 dark:bg-slate-900/80 border-b border-slate-200/80 dark:border-slate-800/80 px-4 sm:px-6 py-3 transition-colors duration-200">
                <div className="flex items-center justify-between gap-4">
                    <!-- Left: Mobile Menu Trigger + Clinic Badge -->
                    <div className="flex items-center gap-3">
                        <button 
                            type="button" 
                            onClick=${() => window.handleSidebarToggle && window.handleSidebarToggle()}
                            className="lg:hidden p-2 rounded-xl text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                            aria-label="Toggle menu"
                        >
                            <i className="fas fa-bars text-lg"></i>
                        </button>
                        
                        <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full bg-sky-50 dark:bg-sky-950/60 border border-sky-200/60 dark:border-sky-800/50 text-xs font-semibold text-sky-700 dark:text-sky-300">
                            <span className="relative flex h-2 w-2">
                                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                            </span>
                            <span>System Active</span>
                        </div>
                    </div>

                    <!-- Center: Digital Live Clock & Date -->
                    <div className="hidden md:flex items-center gap-3 px-4 py-1.5 rounded-xl bg-slate-100/80 dark:bg-slate-800/60 border border-slate-200/60 dark:border-slate-700/50 text-xs font-mono text-slate-700 dark:text-slate-300 shadow-inner">
                        <i className="far fa-clock text-sky-500"></i>
                        <span className="font-semibold text-slate-900 dark:text-slate-100">${formattedTime}</span>
                        <span className="text-slate-400 dark:text-slate-500">•</span>
                        <span>${formattedDate}</span>
                    </div>

                    <!-- Right: Quick Actions + Theme Switcher + Profile -->
                    <div className="flex items-center gap-2 sm:gap-3">
                        <!-- Quick Actions Dropdown -->
                        <div className="relative">
                            <button 
                                onClick=${() => setQuickActionsOpen(!quickActionsOpen)}
                                className="flex items-center gap-2 px-3 sm:px-4 py-2 rounded-xl bg-sky-600 hover:bg-sky-500 text-white font-medium text-xs sm:text-sm shadow-md shadow-sky-600/20 hover:shadow-lg hover:shadow-sky-600/30 transition-all duration-200"
                            >
                                <i className="fas fa-plus text-xs"></i>
                                <span className="hidden sm:inline">Quick Action</span>
                                <i className="fas fa-chevron-down text-[10px] ml-1"></i>
                            </button>

                            ${quickActionsOpen && html`
                                <div 
                                    className="absolute right-0 mt-2 w-56 rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 shadow-2xl py-2 z-50 animate-dropdown"
                                    onClick=${() => setQuickActionsOpen(false)}
                                >
                                    <div className="px-3 py-1.5 text-[11px] font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500">
                                        Clinical Shortcuts
                                    </div>
                                    <a href="/doctor/add-patient/" className="flex items-center gap-3 px-4 py-2.5 text-xs text-slate-700 dark:text-slate-200 hover:bg-sky-50 dark:hover:bg-slate-700/60 hover:text-sky-600 transition-colors">
                                        <div className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
                                            <i className="fas fa-user-plus text-xs"></i>
                                        </div>
                                        <span>Add New Patient</span>
                                    </a>
                                    <a href="/doctor/schedule-appointment/" className="flex items-center gap-3 px-4 py-2.5 text-xs text-slate-700 dark:text-slate-200 hover:bg-sky-50 dark:hover:bg-slate-700/60 hover:text-sky-600 transition-colors">
                                        <div className="p-1.5 rounded-lg bg-sky-500/10 text-sky-600 dark:text-sky-400">
                                            <i className="fas fa-calendar-plus text-xs"></i>
                                        </div>
                                        <span>Book Appointment</span>
                                    </a>
                                    <a href="/doctor/add-medical-record/" className="flex items-center gap-3 px-4 py-2.5 text-xs text-slate-700 dark:text-slate-200 hover:bg-sky-50 dark:hover:bg-slate-700/60 hover:text-sky-600 transition-colors">
                                        <div className="p-1.5 rounded-lg bg-indigo-500/10 text-indigo-600 dark:text-indigo-400">
                                            <i className="fas fa-file-medical text-xs"></i>
                                        </div>
                                        <span>New Clinical Record</span>
                                    </a>
                                </div>
                            `}
                        </div>

                        <!-- Theme Toggle Button -->
                        <button
                            onClick=${handleThemeToggle}
                            className="p-2.5 rounded-xl border border-slate-200/80 dark:border-slate-700/80 bg-slate-50 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700 transition-all duration-200"
                            title="Toggle dark/light mode"
                            aria-label="Toggle theme"
                        >
                            <i className="fas ${isDark ? 'fa-sun text-amber-400' : 'fa-moon text-indigo-500'} text-sm"></i>
                        </button>
                    </div>
                </div>
            </header>
        `;
    }

    window.CmsTopHeader = TopHeader;
    window.ImhotepTopHeader = TopHeader;

    // Auto mount if placeholder exists
    document.addEventListener('DOMContentLoaded', () => {
        const mountPoint = document.getElementById('react-top-header');
        if (mountPoint) {
            window.mountReactComponent(TopHeader, mountPoint);
        }
    });
})();
