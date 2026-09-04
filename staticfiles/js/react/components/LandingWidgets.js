/**
 * React LandingWidgets Component
 * Live stats counter, interactive feature showcase, and interactive tabs
 */

(function() {
    'use strict';
    const { useState, useEffect } = window.React;
    const html = window.html;

    function LiveStatsWidget() {
        const [stats, setStats] = useState({
            doctors: 12,
            patients: 1540,
            prescriptions: 3820,
            uptime: '99.9%'
        });

        useEffect(() => {
            fetch('/api/landing-stats/')
                .then(r => r.ok ? r.json() : null)
                .then(data => {
                    if (data) {
                        setStats(prev => ({
                            doctors: data.total_doctors || data.doctors_count || prev.doctors,
                            patients: data.total_patients || data.patients_count || prev.patients,
                            prescriptions: data.total_prescriptions || data.prescriptions_count || prev.prescriptions,
                            uptime: '99.9%'
                        }));
                    }
                })
                .catch(() => {});
        }, []);

        const items = [
            { label: 'Registered Patients', val: stats.patients, icon: 'fa-user-group', color: 'from-sky-500 to-blue-600' },
            { label: 'E-Prescriptions Issued', val: stats.prescriptions, icon: 'fa-file-prescription', color: 'from-indigo-500 to-purple-600' },
            { label: 'Active Healthcare Staff', val: stats.doctors, icon: 'fa-user-doctor', color: 'from-emerald-500 to-teal-600' },
            { label: 'System Uptime', val: stats.uptime, icon: 'fa-shield-halved', color: 'from-amber-500 to-orange-600' },
        ];

        return html`
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
                ${items.map(item => html`
                    <div key=${item.label} className="relative overflow-hidden rounded-3xl bg-white/70 dark:bg-slate-800/60 backdrop-blur-xl border border-slate-200/80 dark:border-slate-700/60 p-6 shadow-sm hover:shadow-xl hover:-translate-y-1 transition-all duration-300">
                        <div className="flex items-center justify-between mb-3">
                            <div className="w-10 h-10 rounded-2xl bg-gradient-to-br ${item.color} text-white flex items-center justify-center shadow-md">
                                <i className="fas ${item.icon} text-sm"></i>
                            </div>
                            <span className="flex h-2 w-2 relative">
                                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                            </span>
                        </div>
                        <h4 className="text-2xl sm:text-3xl font-extrabold text-slate-900 dark:text-white tracking-tight">
                            ${typeof item.val === 'number' ? item.val.toLocaleString() : item.val}
                        </h4>
                        <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 mt-1">
                            ${item.label}
                        </p>
                    </div>
                `)}
            </div>
        `;
    }

    function InteractiveFeaturesWidget() {
        const [activeTab, setActiveTab] = useState('doctor');

        const tabs = {
            doctor: {
                title: 'Doctor Clinical Workspace',
                tagline: 'Comprehensive patient insights & seamless record keeping',
                features: [
                    'Patient 360° medical history timeline with instant search',
                    'Bilingual Arabic & English rich-text prescription generator',
                    'Direct PDF export with clinic branding and digital header',
                    'Time-limited secure prescription sharing links'
                ],
                badge: 'For Physicians',
                icon: 'fa-stethoscope'
            },
            assistant: {
                title: 'Clinic Assistant & Reception',
                tagline: 'Effortless front-desk queue & appointment management',
                features: [
                    'Instant patient intake and contact verification',
                    'Interactive daily appointment scheduling & check-in flow',
                    'Slot availability calculator with doctor break schedules',
                    'Real-time status updates synced across devices'
                ],
                badge: 'For Assistants',
                icon: 'fa-clipboard-user'
            },
            privacy: {
                title: 'Privacy & Self-Hosted Freedom',
                tagline: '100% data sovereignty without recurring SaaS fees',
                features: [
                    'Self-host on any Linux server, VPS, or Docker container',
                    'PostgreSQL backend with encrypted credential storage',
                    'Role-based access control protecting medical confidentiality',
                    'Zero third-party telemetry or cloud vendor lock-in'
                ],
                badge: 'Sovereignty',
                icon: 'fa-lock'
            }
        };

        const current = tabs[activeTab];

        return html`
            <div className="space-y-6">
                <!-- Tab Selector Buttons -->
                <div className="flex flex-wrap justify-center gap-3">
                    ${Object.entries(tabs).map(([key, item]) => html`
                        <button
                            key=${key}
                            onClick=${() => setActiveTab(key)}
                            className="flex items-center gap-2.5 px-5 py-3 rounded-2xl font-semibold text-xs sm:text-sm transition-all duration-300 ${activeTab === key ? 'bg-sky-600 text-white shadow-lg shadow-sky-600/30 scale-105' : 'bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700 border border-slate-200 dark:border-slate-700'}"
                        >
                            <i className="fas ${item.icon}"></i>
                            <span>${item.title}</span>
                        </button>
                    `)}
                </div>

                <!-- Active Tab Content Card -->
                <div className="rounded-3xl bg-white/80 dark:bg-slate-800/80 backdrop-blur-2xl border border-slate-200/80 dark:border-slate-700/60 p-8 sm:p-10 shadow-xl transition-all duration-300 animate-fade-in">
                    <div className="max-w-3xl mx-auto">
                        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-sky-50 dark:bg-sky-950 text-sky-600 dark:text-sky-300 text-xs font-bold uppercase tracking-wider mb-4 border border-sky-200/60 dark:border-sky-800/60">
                            ${current.badge}
                        </div>
                        <h3 className="text-2xl sm:text-3xl font-extrabold text-slate-900 dark:text-white">
                            ${current.title}
                        </h3>
                        <p className="text-slate-500 dark:text-slate-400 mt-2 text-sm sm:text-base">
                            ${current.tagline}
                        </p>

                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-8">
                            ${current.features.map(f => html`
                                <div key=${f} className="flex items-start gap-3 p-3.5 rounded-2xl bg-slate-50/80 dark:bg-slate-900/50 border border-slate-100 dark:border-slate-800">
                                    <div className="w-6 h-6 rounded-lg bg-emerald-500/10 text-emerald-600 flex items-center justify-center shrink-0 mt-0.5">
                                        <i className="fas fa-check text-xs"></i>
                                    </div>
                                    <span className="text-xs sm:text-sm font-medium text-slate-700 dark:text-slate-200">
                                        ${f}
                                    </span>
                                </div>
                            `)}
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    const landingExports = {
        LiveStatsWidget,
        InteractiveFeaturesWidget
    };
    window.CmsLanding = landingExports;
    window.ImhotepLanding = landingExports;

    document.addEventListener('DOMContentLoaded', () => {
        const statsMount = document.getElementById('react-live-stats');
        if (statsMount) {
            window.mountReactComponent(LiveStatsWidget, statsMount);
        }
        const featuresMount = document.getElementById('react-interactive-features');
        if (featuresMount) {
            window.mountReactComponent(InteractiveFeaturesWidget, featuresMount);
        }
    });
})();
