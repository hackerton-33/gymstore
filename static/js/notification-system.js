/**
 * Enhanced Notification System
 * Handles real-time notifications, toast popups, and notification bell
 */

class NotificationSystem {
    constructor() {
        this.notificationCount = 0;
        this.notifications = [];
        this.toastContainer = null;
        this.init();
    }

    init() {
        // Create toast container
        this.createToastContainer();
        
        // Load initial notifications
        this.loadNotifications();
        
        // Set up periodic refresh (every 15 seconds)
        setInterval(() => this.loadNotifications(), 15000);
        
        // Listen for custom notification events
        document.addEventListener('showNotification', (e) => {
            this.showToast(e.detail.title, e.detail.message, e.detail.type);
        });
    }

    createToastContainer() {
        if (!document.getElementById('toast-notification-container')) {
            const container = document.createElement('div');
            container.id = 'toast-notification-container';
            container.style.cssText = `
                position: fixed;
                top: 80px;
                right: 20px;
                z-index: 9999;
                max-width: 400px;
            `;
            document.body.appendChild(container);
            this.toastContainer = container;
        } else {
            this.toastContainer = document.getElementById('toast-notification-container');
        }
    }

    loadNotifications() {
        fetch('/api/notifications?limit=10')
            .then(response => response.json())
            .then(data => {
                this.notifications = data.notifications || [];
                this.notificationCount = data.unread_count || 0;
                this.updateBadge();
                this.updateDropdown();
            })
            .catch(error => console.error('Error loading notifications:', error));
    }

    updateBadge() {
        const badge = document.getElementById('notification-count');
        if (badge) {
            if (this.notificationCount > 0) {
                badge.textContent = this.notificationCount > 99 ? '99+' : this.notificationCount;
                badge.style.display = 'block';
            } else {
                badge.style.display = 'none';
            }
        }
    }

    updateDropdown() {
        // This will be called when dropdown is opened
        // Implementation depends on your dropdown structure
    }

    showToast(title, message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast-notification toast-${type}`;
        
        const icons = {
            success: 'fa-check-circle',
            error: 'fa-times-circle',
            warning: 'fa-exclamation-triangle',
            info: 'fa-info-circle'
        };
        
        const colors = {
            success: '#10b981',
            error: '#ef4444',
            warning: '#f59e0b',
            info: '#3b82f6'
        };

        toast.innerHTML = `
            <div style="display: flex; align-items: start; gap: 12px; background: white; padding: 16px; border-radius: 12px; box-shadow: 0 10px 40px rgba(0,0,0,0.15); border-left: 4px solid ${colors[type]}; animation: slideInRight 0.3s ease;">
                <i class="fas ${icons[type]}" style="color: ${colors[type]}; font-size: 24px; margin-top: 2px;"></i>
                <div style="flex: 1;">
                    <h6 style="margin: 0 0 4px 0; font-weight: 600; color: #1f2937;">${title}</h6>
                    <p style="margin: 0; font-size: 14px; color: #6b7280;">${message}</p>
                </div>
                <button onclick="this.parentElement.parentElement.remove()" style="background: none; border: none; color: #9ca3af; cursor: pointer; font-size: 18px; padding: 0; width: 24px; height: 24px;">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        `;

        this.toastContainer.appendChild(toast);

        // Auto remove after 5 seconds
        setTimeout(() => {
            toast.style.animation = 'slideOutRight 0.3s ease';
            setTimeout(() => toast.remove(), 300);
        }, 5000);
    }

    // Trigger notification for specific actions
    static notify(title, message, type = 'info') {
        const event = new CustomEvent('showNotification', {
            detail: { title, message, type }
        });
        document.dispatchEvent(event);
    }
}

// Initialize notification system
let notificationSystem;
document.addEventListener('DOMContentLoaded', function() {
    notificationSystem = new NotificationSystem();
});

// Add CSS animations
const style = document.createElement('style');
style.textContent = `
    @keyframes slideInRight {
        from {
            transform: translateX(400px);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }

    @keyframes slideOutRight {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(400px);
            opacity: 0;
        }
    }

    .toast-notification {
        margin-bottom: 12px;
    }

    @media (max-width: 768px) {
        #toast-notification-container {
            right: 10px;
            left: 10px;
            max-width: none;
        }
    }
`;
document.head.appendChild(style);

// Export for use in other scripts
window.NotificationSystem = NotificationSystem;
