/**
 * React SharePrescriptionModal Component
 * Interactive modal to configure expiration, generate share URL, and copy link
 */

(function() {
    'use strict';
    const { useState } = window.React;
    const html = window.html;

    function SharePrescriptionModal({ recordId, patientName, initialShareable, initialShareUrl, initialExpires, csrfToken, onClose }) {
        const [isShareable, setIsShareable] = useState(initialShareable || false);
        const [shareUrl, setShareUrl] = useState(initialShareUrl || '');
        const [expiryOption, setExpiryOption] = useState('24h');
        const [customExpires, setCustomExpires] = useState('');
        const [loading, setLoading] = useState(false);
        const [copied, setCopied] = useState(false);

        const handleToggle = async (action) => {
            setLoading(true);
            try {
                const formData = new FormData();
                formData.append('csrfmiddlewaretoken', csrfToken);
                formData.append('action', action);

                if (action === 'enable') {
                    if (expiryOption === 'never') {
                        formData.append('never_expires', 'true');
                    } else if (expiryOption === '1h') {
                        const d = new Date(Date.now() + 3600 * 1000);
                        formData.append('expires_at', d.toISOString());
                    } else if (expiryOption === '24h') {
                        const d = new Date(Date.now() + 24 * 3600 * 1000);
                        formData.append('expires_at', d.toISOString());
                    } else if (expiryOption === '7d') {
                        const d = new Date(Date.now() + 7 * 24 * 3600 * 1000);
                        formData.append('expires_at', d.toISOString());
                    } else if (expiryOption === 'custom' && customExpires) {
                        formData.append('expires_at', new Date(customExpires).toISOString());
                    }
                }

                const res = await fetch(`/doctor/prescription/toggle-share/${recordId}/`, {
                    method: 'POST',
                    body: formData
                });

                const data = await res.json();
                if (data.status === 'success') {
                    setIsShareable(data.is_shareable);
                    setShareUrl(data.share_url);
                    if (window.showNotification) {
                        window.showNotification(data.message, 'success');
                    }
                } else {
                    if (window.showNotification) {
                        window.showNotification(data.message || 'Error toggling share', 'error');
                    }
                }
            } catch (err) {
                console.error(err);
                if (window.showNotification) {
                    window.showNotification('Network error occurred', 'error');
                }
            } finally {
                setLoading(false);
            }
        };

        const copyToClipboard = () => {
            if (!shareUrl) return;
            navigator.clipboard.writeText(shareUrl).then(() => {
                setCopied(true);
                setTimeout(() => setCopied(false), 2500);
                if (window.showNotification) {
                    window.showNotification('Prescription link copied to clipboard!', 'success');
                }
            });
        };

        return html`
            <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-fade-in">
                <div className="w-full max-w-lg rounded-3xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 shadow-2xl p-6 sm:p-8 relative">
                    <!-- Close button -->
                    <button 
                        onClick=${onClose}
                        className="absolute right-5 top-5 p-2 rounded-xl text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
                    >
                        <i className="fas fa-times"></i>
                    </button>

                    <!-- Header -->
                    <div className="flex items-center gap-3 mb-6">
                        <div className="p-3 rounded-2xl bg-sky-500/10 text-sky-600 dark:text-sky-400 text-xl">
                            <i className="fas fa-share-nodes"></i>
                        </div>
                        <div>
                            <h3 className="text-lg font-bold text-slate-900 dark:text-white">
                                Share Prescription
                            </h3>
                            <p className="text-xs text-slate-500">
                                Patient: <strong className="text-slate-700 dark:text-slate-300">${patientName}</strong>
                            </p>
                        </div>
                    </div>

                    <!-- Expiration Options -->
                    <div className="space-y-4">
                        <div>
                            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">
                                Link Expiration
                            </label>
                            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                                ${['1h', '24h', '7d', 'never'].map(opt => html`
                                    <button
                                        key=${opt}
                                        type="button"
                                        onClick=${() => setExpiryOption(opt)}
                                        className="py-2.5 px-3 rounded-xl border text-center font-semibold transition-all ${expiryOption === opt ? 'border-sky-500 bg-sky-50 dark:bg-sky-950/60 text-sky-700 dark:text-sky-300 shadow-sm' : 'border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-50'}"
                                    >
                                        ${opt === '1h' ? '1 Hour' : opt === '24h' ? '24 Hours' : opt === '7d' ? '7 Days' : 'Forever'}
                                    </button>
                                `)}
                            </div>
                        </div>

                        <!-- Action Button (Enable / Disable) -->
                        <div className="pt-2 flex items-center gap-3">
                            <button
                                onClick=${() => handleToggle(isShareable ? 'disable' : 'enable')}
                                disabled=${loading}
                                className="flex-1 py-3 px-4 rounded-xl font-semibold text-xs text-white shadow-md transition-all ${isShareable ? 'bg-rose-600 hover:bg-rose-500 shadow-rose-600/20' : 'bg-sky-600 hover:bg-sky-500 shadow-sky-600/20'}"
                            >
                                ${loading ? html`<i className="fas fa-spinner fa-spin mr-2"></i> Updating...` : 
                                  isShareable ? html`<i className="fas fa-ban mr-2"></i> Disable Share Link` : 
                                  html`<i className="fas fa-link mr-2"></i> Generate Active Share Link`}
                            </button>
                        </div>

                        <!-- Active Link Box -->
                        ${isShareable && shareUrl && html`
                            <div className="mt-4 p-4 rounded-2xl bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-700 space-y-3 animate-fade-in">
                                <div className="flex items-center justify-between text-xs">
                                    <span className="font-semibold text-emerald-600 dark:text-emerald-400 flex items-center gap-1.5">
                                        <i className="fas fa-check-circle"></i>
                                        Link Active & Accessible
                                    </span>
                                </div>
                                <div className="flex items-center gap-2">
                                    <input 
                                        type="text" 
                                        readOnly 
                                        value=${shareUrl}
                                        className="flex-1 px-3 py-2 text-xs font-mono rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 select-all"
                                    />
                                    <button
                                        onClick=${copyToClipboard}
                                        className="px-4 py-2 rounded-xl text-xs font-semibold text-white bg-slate-900 dark:bg-sky-600 hover:bg-slate-800 transition-colors shrink-0"
                                    >
                                        ${copied ? html`<i className="fas fa-check text-emerald-400 mr-1"></i> Copied` : html`<i className="fas fa-copy mr-1"></i> Copy`}
                                    </button>
                                </div>
                                <div className="flex items-center justify-between text-[11px] text-slate-500">
                                    <span>Patients can view or download this PDF without logging in.</span>
                                    <a href=${shareUrl} target="_blank" className="text-sky-600 hover:underline flex items-center gap-1">
                                        Open <i className="fas fa-external-link-alt text-[9px]"></i>
                                    </a>
                                </div>
                            </div>
                        `}
                    </div>
                </div>
            </div>
        `;
    }

    window.openSharePrescriptionModal = function(props) {
        let mountNode = document.getElementById('react-share-modal-container');
        if (!mountNode) {
            mountNode = document.createElement('div');
            mountNode.id = 'react-share-modal-container';
            document.body.appendChild(mountNode);
        }

        const handleClose = () => {
            if (mountNode._reactRoot) {
                mountNode._reactRoot.unmount();
                mountNode._reactRoot = null;
            }
            mountNode.innerHTML = '';
        };

        window.mountReactComponent(
            () => html`<${SharePrescriptionModal} ...${props} onClose=${handleClose} />`,
            mountNode
        );
    };
})();
