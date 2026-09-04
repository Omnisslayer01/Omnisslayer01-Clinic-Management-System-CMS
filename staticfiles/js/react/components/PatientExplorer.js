/**
 * React PatientExplorer Component
 * Provides real-time search, sorting, Grid/Table view toggles, and quick clinical actions
 */

(function() {
    'use strict';
    const { useState, useMemo } = window.React;
    const html = window.html;

    function PatientExplorer({ initialPatients = [], addPatientUrl = '/doctor/add-patient/' }) {
        const [query, setQuery] = useState('');
        const [genderFilter, setGenderFilter] = useState('all');
        const [viewMode, setViewMode] = useState('grid'); // 'grid' or 'table'
        const [sortBy, setSortBy] = useState('name-asc');

        const filteredPatients = useMemo(() => {
            let result = initialPatients.filter(p => {
                const matchesQuery = !query || 
                    (p.name && p.name.toLowerCase().includes(query.toLowerCase())) ||
                    (p.phone && p.phone.includes(query)) ||
                    (p.id && String(p.id).includes(query));
                
                const matchesGender = genderFilter === 'all' || 
                    (p.gender && p.gender.toLowerCase() === genderFilter.toLowerCase());

                return matchesQuery && matchesGender;
            });

            // Sorting
            result.sort((a, b) => {
                if (sortBy === 'name-asc') return (a.name || '').localeCompare(b.name || '');
                if (sortBy === 'name-desc') return (b.name || '').localeCompare(a.name || '');
                if (sortBy === 'newest') return (new Date(b.date_added || 0)) - (new Date(a.date_added || 0));
                if (sortBy === 'oldest') return (new Date(a.date_added || 0)) - (new Date(b.date_added || 0));
                return 0;
            });

            return result;
        }, [initialPatients, query, genderFilter, sortBy]);

        return html`
            <div className="space-y-6">
                <!-- Toolbar: Search Bar, Gender Pill, Sort Dropdown, View Toggle, Add Button -->
                <div className="p-4 rounded-2xl bg-white dark:bg-slate-800/90 border border-slate-200/80 dark:border-slate-700/60 shadow-sm flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                    <!-- Search Input -->
                    <div className="relative flex-1 max-w-md">
                        <i className="fas fa-search absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 text-sm"></i>
                        <input 
                            type="text"
                            value=${query}
                            onChange=${(e) => setQuery(e.target.value)}
                            placeholder="Instant search by name, phone, or ID..."
                            className="w-full pl-10 pr-4 py-2 rounded-xl text-sm bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-700 text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-sky-500"
                        />
                        ${query && html`
                            <button 
                                onClick=${() => setQuery('')}
                                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 text-xs"
                            >
                                <i className="fas fa-times"></i>
                            </button>
                        `}
                    </div>

                    <!-- Filters & Controls -->
                    <div className="flex flex-wrap items-center gap-3">
                        <!-- Gender Filter -->
                        <div className="flex p-1 rounded-xl bg-slate-100 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-700 text-xs">
                            <button 
                                onClick=${() => setGenderFilter('all')}
                                className="px-3 py-1.5 rounded-lg font-medium transition-all ${genderFilter === 'all' ? 'bg-white dark:bg-slate-800 text-sky-600 shadow-sm' : 'text-slate-500'}"
                            >
                                All
                            </button>
                            <button 
                                onClick=${() => setGenderFilter('male')}
                                className="px-3 py-1.5 rounded-lg font-medium transition-all ${genderFilter === 'male' ? 'bg-white dark:bg-slate-800 text-sky-600 shadow-sm' : 'text-slate-500'}"
                            >
                                Male
                            </button>
                            <button 
                                onClick=${() => setGenderFilter('female')}
                                className="px-3 py-1.5 rounded-lg font-medium transition-all ${genderFilter === 'female' ? 'bg-white dark:bg-slate-800 text-sky-600 shadow-sm' : 'text-slate-500'}"
                            >
                                Female
                            </button>
                        </div>

                        <!-- Sort By -->
                        <select 
                            value=${sortBy}
                            onChange=${(e) => setSortBy(e.target.value)}
                            className="px-3 py-2 rounded-xl text-xs bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 focus:outline-none focus:ring-2 focus:ring-sky-500"
                        >
                            <option value="name-asc">Name (A → Z)</option>
                            <option value="name-desc">Name (Z → A)</option>
                            <option value="newest">Newest Added</option>
                            <option value="oldest">Oldest Added</option>
                        </select>

                        <!-- View Mode Switcher -->
                        <div className="flex p-1 rounded-xl bg-slate-100 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-700 text-xs">
                            <button 
                                onClick=${() => setViewMode('grid')}
                                className="p-1.5 px-2.5 rounded-lg transition-all ${viewMode === 'grid' ? 'bg-white dark:bg-slate-800 text-sky-600 shadow-sm' : 'text-slate-400'}"
                                title="Grid View"
                            >
                                <i className="fas fa-th-large"></i>
                            </button>
                            <button 
                                onClick=${() => setViewMode('table')}
                                className="p-1.5 px-2.5 rounded-lg transition-all ${viewMode === 'table' ? 'bg-white dark:bg-slate-800 text-sky-600 shadow-sm' : 'text-slate-400'}"
                                title="Table View"
                            >
                                <i className="fas fa-list"></i>
                            </button>
                        </div>

                        <!-- Add Patient Action -->
                        <a 
                            href=${addPatientUrl}
                            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-sky-600 hover:bg-sky-500 text-white font-medium text-xs shadow-md shadow-sky-600/20 hover:shadow-lg transition-all"
                        >
                            <i className="fas fa-plus"></i>
                            <span>Add Patient</span>
                        </a>
                    </div>
                </div>

                <!-- Patient Results Banner -->
                <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400 px-1">
                    <span>Showing <strong className="text-slate-900 dark:text-slate-100">${filteredPatients.length}</strong> registered patients</span>
                    ${query && html`<span>Filtered for "${query}"</span>`}
                </div>

                <!-- Empty State -->
                ${filteredPatients.length === 0 ? html`
                    <div className="p-16 rounded-2xl bg-white dark:bg-slate-800/90 border border-slate-200/80 dark:border-slate-700/60 text-center">
                        <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-sky-50 dark:bg-sky-950/60 flex items-center justify-center text-sky-500 text-2xl">
                            <i className="fas fa-user-slash"></i>
                        </div>
                        <h4 className="text-base font-bold text-slate-800 dark:text-slate-200">No Patients Found</h4>
                        <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">No registered records match your query. Try resetting your search filters or register a new patient.</p>
                        <button 
                            onClick=${() => { setQuery(''); setGenderFilter('all'); }}
                            className="mt-4 px-4 py-2 rounded-xl bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-200 text-xs font-medium hover:bg-slate-200 transition-colors"
                        >
                            Clear Filters
                        </button>
                    </div>
                ` : viewMode === 'grid' ? html`
                    <!-- Grid View Cards -->
                    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
                        ${filteredPatients.map(p => html`
                            <div key=${p.id} className="group relative rounded-2xl bg-white dark:bg-slate-800/90 border border-slate-200/80 dark:border-slate-700/60 p-5 shadow-sm hover:shadow-xl hover:-translate-y-1 transition-all duration-300 flex flex-col justify-between">
                                <div>
                                    <!-- Card Header: Avatar, Name, Gender Badge -->
                                    <div className="flex items-start justify-between gap-3">
                                        <div className="flex items-center gap-3">
                                            <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-sky-400 to-indigo-600 text-white font-bold flex items-center justify-center text-lg shadow-md group-hover:scale-105 transition-transform">
                                                ${p.name ? p.name.charAt(0).toUpperCase() : 'P'}
                                            </div>
                                            <div>
                                                <a href=${p.detail_url || '#'} className="font-bold text-base text-slate-900 dark:text-white group-hover:text-sky-600 dark:group-hover:text-sky-400 transition-colors">
                                                    ${p.name}
                                                </a>
                                                <p className="text-xs text-slate-500 dark:text-slate-400">
                                                    ${p.age ? `${p.age} yrs` : ''} ${p.age && p.date_of_birth ? '•' : ''} ${p.date_of_birth || ''}
                                                </p>
                                            </div>
                                        </div>

                                        <span className="px-2.5 py-1 rounded-full text-[11px] font-semibold ${p.gender && p.gender.toLowerCase() === 'female' ? 'bg-pink-50 dark:bg-pink-950/60 text-pink-700 dark:text-pink-300 border border-pink-200 dark:border-pink-800' : 'bg-blue-50 dark:bg-blue-950/60 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800'}">
                                            ${p.gender || 'Unknown'}
                                        </span>
                                    </div>

                                    <!-- Patient Details Preview -->
                                    <div className="mt-4 space-y-2 text-xs text-slate-600 dark:text-slate-300">
                                        ${p.phone && html`
                                            <div className="flex items-center gap-2">
                                                <i className="fas fa-phone text-sky-500 w-4"></i>
                                                <a href=${`tel:${p.phone}`} className="hover:underline font-mono">${p.phone}</a>
                                            </div>
                                        `}
                                        ${p.address && html`
                                            <div className="flex items-center gap-2 truncate">
                                                <i className="fas fa-map-marker-alt text-rose-500 w-4"></i>
                                                <span className="truncate">${p.address}</span>
                                            </div>
                                        `}
                                    </div>
                                </div>

                                <!-- Card Footer Actions -->
                                <div className="mt-5 pt-4 border-t border-slate-100 dark:border-slate-700/60 flex items-center justify-between gap-2">
                                    <a 
                                        href=${p.detail_url || '#'}
                                        className="text-xs font-semibold text-sky-600 dark:text-sky-400 hover:text-sky-700 flex items-center gap-1 group-hover:translate-x-0.5 transition-transform"
                                    >
                                        <span>Patient 360°</span>
                                        <i className="fas fa-arrow-right text-[10px]"></i>
                                    </a>

                                    <div className="flex items-center gap-1.5">
                                        <a 
                                            href=${p.edit_url || '#'}
                                            className="p-2 rounded-xl text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
                                            title="Edit Patient"
                                        >
                                            <i className="fas fa-pen text-xs"></i>
                                        </a>
                                        <a 
                                            href=${p.schedule_url || '#'}
                                            className="p-2 rounded-xl text-sky-600 hover:bg-sky-50 dark:hover:bg-sky-950/60 transition-colors"
                                            title="Book Appointment"
                                        >
                                            <i className="fas fa-calendar-plus text-xs"></i>
                                        </a>
                                    </div>
                                </div>
                            </div>
                        `)}
                    </div>
                ` : html`
                    <!-- Table View -->
                    <div className="overflow-hidden rounded-2xl bg-white dark:bg-slate-800/90 border border-slate-200/80 dark:border-slate-700/60 shadow-sm">
                        <div className="overflow-x-auto">
                            <table className="min-w-full divide-y divide-slate-200/70 dark:divide-slate-700/60 text-left text-xs">
                                <thead className="bg-slate-50 dark:bg-slate-900/60 text-slate-500 font-semibold uppercase tracking-wider">
                                    <tr>
                                        <th className="px-6 py-3.5">Patient</th>
                                        <th className="px-6 py-3.5">Gender</th>
                                        <th className="px-6 py-3.5">Phone</th>
                                        <th className="px-6 py-3.5">Address</th>
                                        <th className="px-6 py-3.5">Added Date</th>
                                        <th className="px-6 py-3.5 text-right">Actions</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                                    ${filteredPatients.map(p => html`
                                        <tr key=${p.id} className="hover:bg-sky-50/40 dark:hover:bg-slate-700/30 transition-colors">
                                            <td className="px-6 py-4">
                                                <div className="flex items-center gap-3">
                                                    <div className="w-8 h-8 rounded-full bg-sky-600 text-white font-bold flex items-center justify-center text-xs">
                                                        ${p.name ? p.name.charAt(0).toUpperCase() : 'P'}
                                                    </div>
                                                    <div>
                                                        <a href=${p.detail_url || '#'} className="font-bold text-slate-900 dark:text-white hover:text-sky-600">
                                                            ${p.name}
                                                        </a>
                                                        <p className="text-[11px] text-slate-500">${p.age ? `${p.age} yrs` : ''}</p>
                                                    </div>
                                                </div>
                                            </td>
                                            <td className="px-6 py-4">
                                                <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold ${p.gender && p.gender.toLowerCase() === 'female' ? 'bg-pink-50 text-pink-700' : 'bg-blue-50 text-blue-700'}">
                                                    ${p.gender || '—'}
                                                </span>
                                            </td>
                                            <td className="px-6 py-4 font-mono">${p.phone || '—'}</td>
                                            <td className="px-6 py-4 text-slate-500 max-w-xs truncate">${p.address || '—'}</td>
                                            <td className="px-6 py-4 text-slate-500">${p.date_added || '—'}</td>
                                            <td className="px-6 py-4 text-right">
                                                <div className="flex items-center justify-end gap-2">
                                                    <a href=${p.detail_url || '#'} className="px-2.5 py-1 rounded-lg bg-sky-50 dark:bg-sky-950/60 text-sky-600 text-xs font-medium hover:bg-sky-100">
                                                        Details
                                                    </a>
                                                    <a href=${p.edit_url || '#'} className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600">
                                                        <i className="fas fa-pen"></i>
                                                    </a>
                                                </div>
                                            </td>
                                        </tr>
                                    `)}
                                </tbody>
                            </table>
                        </div>
                    </div>
                `}
            </div>
        `;
    }

    window.CmsPatientExplorer = PatientExplorer;
    window.ImhotepPatientExplorer = PatientExplorer;
})();
