/**
 * React Toast Notification System
 * Renders modern animated toasts with icon, countdown bar, and dismiss
 */

(function() {
    'use strict';
    const { useState, useEffect } = window.React;
    const html = window.html;

    function Toast({ toast, onDismiss }) {
        const [progress, setProgress] = useState(100);

        useEffect(() => {
            const start = Date.now();
            const duration = toast.duration || 5000;
            const interval = setInterval(() => {
                const elapsed = Date.now() - start;
                const remaining = Math.max(0, 100 - (elapsed / duration) * 100);
                setProgress(remaining);
                if (remaining === 0) {
                    clearInterval(interval);
                    onDismiss(toast.id);
                }
            }, 50);

            return () => clearInterval(interval);
        }, [toast, onDismiss]);

        const typeStyles = {
            success: {
                bg: 'bg-emerald-50 dark:bg-emerald-950/80 border-emerald-300 dark:border-emerald-800 text-emerald-900 dark:text-emerald-100',
                iconBg: 'bg-emerald-500 text-white',
                icon: 'fa-check',
                bar: 'bg-emerald-500'
            },
            error: {
                bg: 'bg-rose-50 dark:bg-rose-950/80 border-rose-300 dark:border-rose-800 text-rose-900 dark:text-rose-100',
                iconBg: 'bg-rose-500 text-white',
                icon: 'fa-exclamation-circle',
                bar: 'bg-rose-500'
            },
            warning: {
                bg: 'bg-amber-50 dark:bg-amber-950/80 border-amber-300 dark:border-amber-800 text-amber-900 dark:text-amber-100',
                iconBg: 'bg-amber-500 text-white',
                icon: 'fa-triangle-exclamation',
                bar: 'bg-amber-500'
            },
            info: {
                bg: 'bg-sky-50 dark:bg-sky-950/80 border-sky-300 dark:border-sky-800 text-sky-900 dark:text-sky-100',
                iconBg: 'bg-sky-500 text-white',
                icon: 'fa-info-circle',
                bar: 'bg-sky-500'
            }
        };

        const config = typeStyles[toast.type] || typeStyles.info;

        return html`
            <div className="relative overflow-hidden rounded-xl border shadow-xl backdrop-blur-md transition-all duration-300 animate-slide-in pointer-events-auto p-4 ${config.bg} max-w-sm w-full flex items-start gap-3">
                <div className="p-2 rounded-lg ${config.iconBg} flex items-center justify-center shrink-0 w-8 h-8 shadow-sm">
                    <i className="fas ${config.icon} text-sm"></i>
                </div>
                <div className="flex-1 text-sm font-medium pr-2">
                    ${toast.message}
                </div>
                <button 
                    onClick=${() => onDismiss(toast.id)}
                    className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition-colors p-1"
                    aria-label="Close"
                >
                    <i className="fas fa-times text-xs"></i>
                </button>
                <div 
                    className="absolute bottom-0 left-0 h-1 transition-all ease-linear ${config.bar}"
                    style=${{ width: progress + '%' }}
                />
            </div>
        `;
    }

    function ToastContainer() {
        const [toasts, setToasts] = useState([]);

        useEffect(() => {
            const bus = window.CmsToasts || window.ImhotepToasts;
            if (!bus) return;
            const unsubscribe = bus.subscribe(newToast => {
                setToasts(prev => [newToast, ...prev.slice(0, 4)]);
            });
            return unsubscribe;
        }, []);

        const dismiss = (id) => {
            setToasts(prev => prev.filter(t => t.id !== id));
        };

        return html`
            <div className="fixed top-5 right-5 z-[9999] flex flex-col gap-2 pointer-events-none w-full max-w-sm px-4">
                ${toasts.map(toast => html`
                    <${Toast} key=${toast.id} toast=${toast} onDismiss=${dismiss} />
                `)}
            </div>
        `;
    }

    // Auto mount to body or #toast-container
    document.addEventListener('DOMContentLoaded', () => {
        let container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            document.body.appendChild(container);
        }
        window.mountReactComponent(ToastContainer, container);
    });
})();
