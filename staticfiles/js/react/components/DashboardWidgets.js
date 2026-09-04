/**
 * React Dashboard Widgets Component
 * Interactive Stat Cards, Live Metric Sparklines, and Appointment Management
 */

(function() {
    'use strict';
    const { useState, useMemo } = window.React;
    const html = window.html;

    function StatCard({ title, value, subtitle, icon, iconColor, gradient, href, trend }) {
        return html`
            <a 
                href=${href || '#'}
                className="group relative overflow-hidden rounded-2xl bg-white dark:bg-slate-800/90 border border-slate-200/80 dark:border-slate-700/60 p-6 shadow-sm hover:shadow-xl hover:-translate-y-1 transition-all duration-300 block"
            >
                <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-br ${gradient} opacity-10 group-hover:opacity-20 rounded-bl-full transition-opacity pointer-events-none" />
                
                <div className="flex items-start justify-between">
                    <div>
                        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                            ${title}
                        </p>
                        <h3 className="mt-2 text-3xl font-bold tracking-tight text-slate-900 dark:text-white group-hover:text-sky-600 dark:group-hover:text-sky-400 transition-colors">
                            ${value}
                        </h3>
                        ${subtitle && html`
                            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400 flex items-center gap-1">
                                <span>${subtitle}</span>
                            </p>
                        `}
                    </div>
                    
                    <div className="p-3.5 rounded-2xl ${iconColor} shadow-md group-hover:scale-110 transition-transform duration-300">
                        <i className="fas ${icon} text-lg"></i>
                    </div>
                </div>

                ${trend && html`
                    <div className="mt-4 pt-3 border-t border-slate-100 dark:border-slate-700/50 flex items-center justify-between text-xs">
                        <span className="font-medium text-emerald-600 dark:text-emerald-400 flex items-center gap-1">
                            <i className="fas fa-arrow-trend-up"></i>
                            ${trend}
                        </span>
                        <span className="text-slate-400 group-hover:text-sky-600 transition-colors">View details →</span>
                    </div>
                `}
            </a>
        `;
    }

    function AppointmentManager({ initialAppointments = [], csrfToken = '' }) {
        const [filter, setFilter] = useState('all'); // all, pending, completed
        const [search, setSearch] = useState('');
        const [appointments, setAppointments] = useState(initialAppointments);
        const [loadingId, setLoadingId] = useState(null);

        const filteredAppointments = useMemo(() => {
            return appointments.filter(app => {
                const matchesFilter = 
                    filter === 'all' ? true :
                    filter === 'completed' ? (app.status === 'completed') :
                    (app.status !== 'completed');
                
                const matchesSearch = !search || 
                    (app.patient_name && app.patient_name.toLowerCase().includes(search.toLowerCase())) ||
                    (app.phone && app.phone.includes(search));

                return matchesFilter && matchesSearch;
            });
        }, [appointments, filter, search]);

        const handleComplete = async (appId) => {
            setLoadingId(appId);
            try {
                const formData = new FormData();
                formData.append('appointment_id', appId);
                formData.append('csrfmiddlewaretoken', csrfToken);

                const response = await fetch('/doctor/mark-appointment-completed/', {
                    method: 'POST',
                    body: formData
                });

                if (response.ok) {
                    setAppointments(prev => prev.map(a => 
                        a.id === appId ? { ...a, status: 'completed' } : a
                    ));
                    if (window.showNotification) {
                        window.showNotification('Appointment marked as completed!', 'success');
                    }
                } else {
                    if (window.showNotification) {
                        window.showNotification('Failed to update status', 'error');
                    }
                }
            } catch (err) {
                console.error(err);
                if (window.showNotification) {
                    window.showNotification('Network error occurred', 'error');
                }
            } finally {
                setLoadingId(null);
            }
        };

        return html`
            <div className="rounded-2xl bg-white dark:bg-slate-800/90 border border-slate-200/80 dark:border-slate-700/60 shadow-sm overflow-hidden">
                <!-- Header with Tabs and Search -->
                <div className="p-5 border-b border-slate-200/80 dark:border-slate-700/60 flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <div className="flex items-center gap-3">
                        <div className="p-2.5 rounded-xl bg-sky-500/10 text-sky-600 dark:text-sky-400">
                            <i className="fas fa-calendar-check text-lg"></i>
                        </div>
                        <div>
                            <h3 className="text-base font-bold text-slate-900 dark:text-white">
                                Today's Consultations
                            </h3>
                            <p className="text-xs text-slate-500 dark:text-slate-400">
                                Real-time patient schedule & check-in
                            </p>
                        </div>
                    </div>

                    <!-- Actions: Filter Tabs + Search -->
                    <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
                        <!-- Search input -->
                        <div className="relative">
                            <i className="fas fa-search absolute left-3 top-1/2 -translate-y-1/2 text-xs text-slate-400"></i>
                            <input 
                                type="text"
                                value=${search}
                                onChange=${(e) => setSearch(e.target.value)}
                                placeholder="Filter patient..."
                                className="w-full sm:w-44 pl-8 pr-3 py-1.5 rounded-xl text-xs bg-slate-100 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500"
                            />
                        </div>

                        <!-- Status Filter Tabs -->
                        <div className="flex p-1 rounded-xl bg-slate-100 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-700 text-xs">
                            <button 
                                onClick=${() => setFilter('all')}
                                className="px-3 py-1 rounded-lg font-medium transition-all ${filter === 'all' ? 'bg-white dark:bg-slate-800 text-sky-600 shadow-sm' : 'text-slate-500 hover:text-slate-900 dark:hover:text-slate-200'}"
                            >
                                All (${appointments.length})
                            </button>
                            <button 
                                onClick=${() => setFilter('pending')}
                                className="px-3 py-1 rounded-lg font-medium transition-all ${filter === 'pending' ? 'bg-white dark:bg-slate-800 text-sky-600 shadow-sm' : 'text-slate-500 hover:text-slate-900 dark:hover:text-slate-200'}"
                            >
                                Pending
                            </button>
                            <button 
                                onClick=${() => setFilter('completed')}
                                className="px-3 py-1 rounded-lg font-medium transition-all ${filter === 'completed' ? 'bg-white dark:bg-slate-800 text-sky-600 shadow-sm' : 'text-slate-500 hover:text-slate-900 dark:hover:text-slate-200'}"
                            >
                                Done
                            </button>
                        </div>
                    </div>
                </div>

                <!-- Table Content -->
                <div className="overflow-x-auto">
                    ${filteredAppointments.length === 0 ? html`
                        <div className="p-12 text-center">
                            <div className="w-16 h-16 mx-auto mb-3 rounded-2xl bg-sky-50 dark:bg-sky-950/50 flex items-center justify-center text-sky-500">
                                <i className="far fa-calendar-times text-2xl"></i>
                            </div>
                            <p className="text-sm font-semibold text-slate-800 dark:text-slate-200">No appointments found</p>
                            <p className="text-xs text-slate-500 mt-1">No scheduled visits match the current criteria.</p>
                        </div>
                    ` : html`
                        <table className="min-w-full divide-y divide-slate-200/70 dark:divide-slate-700/60 text-left text-xs">
                            <thead className="bg-slate-50/70 dark:bg-slate-900/40 text-slate-500 dark:text-slate-400 font-semibold uppercase tracking-wider">
                                <tr>
                                    <th className="px-6 py-3.5">Patient</th>
                                    <th className="px-6 py-3.5">Slot Time</th>
                                    <th className="px-6 py-3.5">Status</th>
                                    <th className="px-6 py-3.5">Notes</th>
                                    <th className="px-6 py-3.5 text-right">Actions</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                                ${filteredAppointments.map(app => html`
                                    <tr key=${app.id} className="hover:bg-sky-50/40 dark:hover:bg-slate-700/30 transition-colors">
                                        <td className="px-6 py-4">
                                            <div className="flex items-center gap-3">
                                                <div className="w-8 h-8 rounded-full bg-gradient-to-br from-sky-400 to-blue-600 text-white font-bold flex items-center justify-center text-xs shadow-sm">
                                                    ${app.patient_name ? app.patient_name.charAt(0).toUpperCase() : 'P'}
                                                </div>
                                                <div>
                                                    <a href=${app.detail_url || '#'} className="font-semibold text-slate-900 dark:text-slate-100 hover:text-sky-600 dark:hover:text-sky-400">
                                                        ${app.patient_name}
                                                    </a>
                                                    ${app.phone && html`
                                                        <p className="text-[11px] text-slate-500">${app.phone}</p>
                                                    `}
                                                </div>
                                            </div>
                                        </td>
                                        <td className="px-6 py-4 font-mono font-medium text-slate-700 dark:text-slate-300">
                                            <i className="far fa-clock text-slate-400 mr-1.5"></i>
                                            ${app.start_time} - ${app.end_time}
                                        </td>
                                        <td className="px-6 py-4">
                                            ${app.status === 'completed' ? html`
                                                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800/60">
                                                    <i className="fas fa-check-circle text-[10px]"></i>
                                                    Completed
                                                </span>
                                            ` : html`
                                                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-sky-50 dark:bg-sky-950/60 text-sky-700 dark:text-sky-300 border border-sky-200 dark:border-sky-800/60">
                                                    <span className="w-1.5 h-1.5 rounded-full bg-sky-500 animate-pulse"></span>
                                                    Scheduled
                                                </span>
                                            `}
                                        </td>
                                        <td className="px-6 py-4 text-slate-600 dark:text-slate-400 max-w-xs truncate">
                                            ${app.notes || '—'}
                                        </td>
                                        <td className="px-6 py-4 text-right">
                                            <div className="flex items-center justify-end gap-2">
                                                ${app.status !== 'completed' && html`
                                                    <button 
                                                        onClick=${() => handleComplete(app.id)}
                                                        disabled=${loadingId === app.id}
                                                        className="px-2.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-medium text-[11px] shadow-sm transition-all"
                                                        title="Mark Completed"
                                                    >
                                                        ${loadingId === app.id ? html`<i className="fas fa-spinner fa-spin"></i>` : html`<i className="fas fa-check mr-1"></i> Done`}
                                                    </button>
                                                `}
                                                <a 
                                                    href=${app.update_url || '#'}
                                                    className="p-1.5 rounded-lg border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700"
                                                    title="Reschedule / Edit"
                                                >
                                                    <i className="fas fa-edit"></i>
                                                </a>
                                            </div>
                                        </td>
                                    </tr>
                                `)}
                            </tbody>
                        </table>
                    `}
                </div>
            </div>
        `;
    }

    const dashboardExports = {
        StatCard,
        AppointmentManager
    };
    window.CmsDashboard = dashboardExports;
    window.ImhotepDashboard = dashboardExports;
})();
