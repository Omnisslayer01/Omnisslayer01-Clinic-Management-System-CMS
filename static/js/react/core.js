/**
 * Clinic Management System (CMS) - React Core Runtime Engine
 * Initializes React 18, HTM template binding, and global component registry
 */

(function() {
    'use strict';

    if (!window.React || !window.ReactDOM) {
        console.error('React or ReactDOM is not loaded.');
        return;
    }

    const { createElement, useState, useEffect, useMemo, useRef, useCallback } = window.React;

    // Bind HTM to React.createElement for zero-build, ultra-fast JSX-like templates
    const html = window.htm ? window.htm.bind(createElement) : null;
    window.html = html;

    // Modern React Component Registry & Mounting helper
    window.mountReactComponent = function(Component, targetId, props = {}) {
        const container = typeof targetId === 'string' ? document.getElementById(targetId) : targetId;
        if (!container) return null;

        try {
            if (window.ReactDOM.createRoot) {
                if (!container._reactRoot) {
                    container._reactRoot = window.ReactDOM.createRoot(container);
                }
                container._reactRoot.render(createElement(Component, props));
                return container._reactRoot;
            } else {
                window.ReactDOM.render(createElement(Component, props), container);
                return container;
            }
        } catch (err) {
            console.error('Failed to mount React component into #' + targetId, err);
            return null;
        }
    };

    // Global Notification / Toast Event Bus (Dual-aliased: CmsToasts & ImhotepToasts)
    const toastListeners = new Set();
    const toastBus = {
        subscribe(fn) {
            toastListeners.add(fn);
            return () => toastListeners.delete(fn);
        },
        show(message, type = 'info', duration = 5000) {
            toastListeners.forEach(fn => fn({ id: Date.now() + Math.random(), message, type, duration }));
        },
        notify(message, type = 'info', duration = 5000) {
            this.show(message, type, duration);
        },
        error(message, duration = 5000) {
            this.show(message, 'error', duration);
        },
        success(message, duration = 5000) {
            this.show(message, 'success', duration);
        }
    };
    window.CmsToasts = toastBus;
    window.ImhotepToasts = toastBus;

    // Replace or enhance global window.showNotification
    window.showNotification = function(message, type = 'info', duration = 5000) {
        toastBus.show(message, type, duration);
    };

    // Theme Management Helper (Dual-aliased: CmsTheme & ImhotepTheme)
    const themeManager = {
        isDark() {
            return document.documentElement.classList.contains('dark');
        },
        toggle() {
            const isDark = this.isDark();
            if (isDark) {
                document.documentElement.classList.remove('dark');
                localStorage.setItem('color-theme', 'light');
            } else {
                document.documentElement.classList.add('dark');
                localStorage.setItem('color-theme', 'dark');
            }
            window.dispatchEvent(new CustomEvent('theme-changed', { detail: { isDark: !isDark } }));
            return !isDark;
        }
    };
    window.CmsTheme = themeManager;
    window.ImhotepTheme = themeManager;

    console.log('✅ Clinic Management System (CMS) React Engine initialized.');
})();
