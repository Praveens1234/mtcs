/* MTCS — Minimal Custom JavaScript */

// Theme initialization
(function () {
    const theme = localStorage.getItem('theme') || 'dark';
    if (theme === 'dark' || (theme === 'auto' && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
        document.documentElement.classList.add('dark');
    }
})();

// SSE Auto-reconnect
class SSEManager {
    constructor(url, handlers = {}) {
        this.url = url;
        this.handlers = handlers;
        this.reconnectDelay = 3000;
        this.maxReconnectDelay = 30000;
        this.eventSource = null;
        this.connect();
    }

    connect() {
        this.eventSource = new EventSource(this.url);

        this.eventSource.onopen = () => {
            this.reconnectDelay = 3000;
            console.log(`SSE connected: ${this.url}`);
        };

        this.eventSource.onerror = () => {
            this.eventSource.close();
            console.warn(`SSE disconnected, reconnecting in ${this.reconnectDelay}ms...`);
            setTimeout(() => this.connect(), this.reconnectDelay);
            this.reconnectDelay = Math.min(this.reconnectDelay * 1.5, this.maxReconnectDelay);
        };

        // Register event handlers
        for (const [event, handler] of Object.entries(this.handlers)) {
            this.eventSource.addEventListener(event, (e) => {
                try {
                    const data = JSON.parse(e.data);
                    handler(data);
                } catch (err) {
                    console.error(`SSE parse error for ${event}:`, err);
                }
            });
        }
    }

    close() {
        if (this.eventSource) {
            this.eventSource.close();
        }
    }
}

// Haptic feedback (mobile)
function haptic(style = 'light') {
    if (navigator.vibrate) {
        const patterns = {
            light: 10,
            medium: 25,
            heavy: 50,
            success: [10, 50, 10],
            error: [50, 50, 50],
        };
        navigator.vibrate(patterns[style] || 10);
    }
}

// Add haptic to buttons
document.addEventListener('click', (e) => {
    const btn = e.target.closest('button, a.nav-tab');
    if (btn) haptic('light');
});

// Format currency
function formatCurrency(value, decimals = 2) {
    if (typeof value !== 'number') return '---';
    const prefix = value >= 0 ? '$' : '-$';
    return prefix + Math.abs(value).toLocaleString(undefined, {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
    });
}

// Format price
function formatPrice(value, digits = 5) {
    if (typeof value !== 'number' || value === 0) return '---';
    return value.toFixed(digits);
}

// HTMX error handling
document.body.addEventListener('htmx:responseError', function (evt) {
    console.error('HTMX error:', evt.detail);
});
