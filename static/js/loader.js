/**
 * Modern Asynchronous Top Progress Bar
 * Similar to YouTube, GitHub, and NProgress
 * Non-blocking, hardware-accelerated, lightweight.
 */
(function () {
  'use strict';

  var progressBar = null;
  var status = null; // null or number between 0 and 1
  var timer = null;
  var resetTimer = null;

  function ensureProgressBar() {
    if (!progressBar) {
      progressBar = document.getElementById('top-progress-bar');
      if (!progressBar) {
        progressBar = document.createElement('div');
        progressBar.id = 'top-progress-bar';
        progressBar.setAttribute('role', 'progressbar');
        progressBar.setAttribute('aria-hidden', 'true');
        document.documentElement.appendChild(progressBar);
      }
    }
    return progressBar;
  }

  function set(n) {
    var bar = ensureProgressBar();
    if (!bar) return;

    n = Math.max(0, Math.min(1, n));
    status = n;

    bar.classList.add('active');
    bar.style.opacity = '1';
    bar.style.transform = 'scaleX(' + n + ')';
  }

  function trickle() {
    if (status === null) return;
    // Slow down as it approaches 90%
    var inc = 0;
    if (status < 0.2) {
      inc = 0.1;
    } else if (status < 0.5) {
      inc = 0.04;
    } else if (status < 0.8) {
      inc = 0.02;
    } else if (status < 0.95) {
      inc = 0.005;
    }
    set(status + inc);
    timer = setTimeout(trickle, 250);
  }

  function start() {
    if (status !== null) return; // already active
    clearTimeout(resetTimer);
    clearTimeout(timer);
    set(0.15);
    timer = setTimeout(trickle, 200);
  }

  function done() {
    if (status === null) return;
    clearTimeout(timer);
    set(1.0);

    resetTimer = setTimeout(function () {
      var bar = ensureProgressBar();
      if (bar) {
        bar.style.opacity = '0';
        setTimeout(function () {
          bar.classList.remove('active');
          bar.style.transform = 'scaleX(0)';
          status = null;
        }, 300);
      } else {
        status = null;
      }
    }, 200);
  }

  // Handle internal navigation clicks for instant tactile response (<5ms)
  document.addEventListener('click', function (event) {
    // Only handle primary (left) clicks without modifier keys
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
      return;
    }

    var anchor = event.target.closest('a');
    if (!anchor) return;

    var href = anchor.getAttribute('href');
    if (!href) return;

    // Skip hash links, mailto, tel, javascript, downloads, target="_blank"
    if (
      href.startsWith('#') ||
      href.startsWith('mailto:') ||
      href.startsWith('tel:') ||
      href.startsWith('javascript:') ||
      anchor.hasAttribute('download') ||
      anchor.target === '_blank'
    ) {
      return;
    }

    // Check same-origin
    var destination;
    try {
      destination = new URL(anchor.href, window.location.href);
    } catch (e) {
      return;
    }

    if (destination.origin !== window.location.origin) {
      return; // External link
    }

    // If same page without hash change, don't trigger
    if (destination.pathname === window.location.pathname && destination.search === window.location.search && destination.hash) {
      return;
    }

    // Valid internal navigation: trigger immediate progress bar
    start();
  });

  // Trigger on form submissions
  document.addEventListener('submit', function (event) {
    var form = event.target;
    if (form && form.target !== '_blank' && !form.classList.contains('no-loader')) {
      start();
    }
  });

  // Finish or hide on page show (handles initial load and bfcache back/forward navigation)
  window.addEventListener('pageshow', function () {
    done();
  });

  // Finish on DOM ready and window load
  document.addEventListener('DOMContentLoaded', done);
  window.addEventListener('load', done);

  // Fallback beforeunload in case navigation wasn't caught by click
  window.addEventListener('beforeunload', function () {
    start();
  });

  // Optional: HTMX support if present
  if (window.htmx) {
    document.body.addEventListener('htmx:beforeRequest', start);
    document.body.addEventListener('htmx:afterOnLoad', done);
    document.body.addEventListener('htmx:responseError', done);
  }

  // Fallback safety: auto-dismiss if network hangs
  setTimeout(done, 12000);

  // Expose global controller
  window.TopProgressBar = {
    start: start,
    done: done,
    set: set,
    status: function () { return status; }
  };
  window.topProgress = window.TopProgressBar;

  // Backwards compatibility for any legacy callers
  window.showLoader = start;
  window.hideLoader = done;
})();

