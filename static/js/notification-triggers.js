/**
 * Notification Triggers
 * Helper functions to trigger notifications for various actions
 */

// Cart notifications
function notifyCartAdd(productName) {
    NotificationSystem.notify('Added to Cart', `${productName} has been added to your cart`, 'success');
}

function notifyCartRemove(productName) {
    NotificationSystem.notify('Removed from Cart', `${productName} has been removed from your cart`, 'info');
}

function notifyCartUpdate() {
    NotificationSystem.notify('Cart Updated', 'Your cart has been updated', 'success');
}

// Profile notifications
function notifyProfileUpdate() {
    NotificationSystem.notify('Profile Updated', 'Your profile information has been saved', 'success');
}

function notifyPasswordChange() {
    NotificationSystem.notify('Password Changed', 'Your password has been updated successfully', 'success');
}

// Order notifications
function notifyOrderPlaced(orderNumber) {
    NotificationSystem.notify('Order Placed', `Order #${orderNumber} has been placed successfully`, 'success');
}

function notifyOrderUpdate(orderNumber, status) {
    NotificationSystem.notify('Order Update', `Order #${orderNumber} is now ${status}`, 'info');
}

// Wishlist notifications
function notifyWishlistAdd(productName) {
    NotificationSystem.notify('Added to Wishlist', `${productName} has been added to your wishlist`, 'success');
}

function notifyWishlistRemove(productName) {
    NotificationSystem.notify('Removed from Wishlist', `${productName} has been removed from your wishlist`, 'info');
}

// System notifications
function notifySystemUpdate(message) {
    NotificationSystem.notify('System Update', message, 'info');
}

function notifyError(message) {
    NotificationSystem.notify('Error', message, 'error');
}

function notifyWarning(message) {
    NotificationSystem.notify('Warning', message, 'warning');
}

function notifySuccess(message) {
    NotificationSystem.notify('Success', message, 'success');
}

// Login/Logout notifications
function notifyLogin(username) {
    NotificationSystem.notify('Welcome Back', `Hello ${username}!`, 'success');
}

function notifyLogout() {
    NotificationSystem.notify('Logged Out', 'You have been logged out successfully', 'info');
}

// Registration notifications
function notifyRegistration() {
    NotificationSystem.notify('Registration Successful', 'Welcome to Daily Fitness!', 'success');
}

// Payment notifications
function notifyPaymentSuccess() {
    NotificationSystem.notify('Payment Successful', 'Your payment has been processed', 'success');
}

function notifyPaymentFailed() {
    NotificationSystem.notify('Payment Failed', 'There was an issue processing your payment', 'error');
}

// Review notifications
function notifyReviewSubmitted() {
    NotificationSystem.notify('Review Submitted', 'Thank you for your feedback!', 'success');
}

// Address notifications
function notifyAddressAdded() {
    NotificationSystem.notify('Address Added', 'New address has been saved', 'success');
}

function notifyAddressUpdated() {
    NotificationSystem.notify('Address Updated', 'Address has been updated', 'success');
}

// Export functions
window.NotificationTriggers = {
    cart: {
        add: notifyCartAdd,
        remove: notifyCartRemove,
        update: notifyCartUpdate
    },
    profile: {
        update: notifyProfileUpdate,
        passwordChange: notifyPasswordChange
    },
    order: {
        placed: notifyOrderPlaced,
        update: notifyOrderUpdate
    },
    wishlist: {
        add: notifyWishlistAdd,
        remove: notifyWishlistRemove
    },
    system: {
        update: notifySystemUpdate,
        error: notifyError,
        warning: notifyWarning,
        success: notifySuccess
    },
    auth: {
        login: notifyLogin,
        logout: notifyLogout,
        register: notifyRegistration
    },
    payment: {
        success: notifyPaymentSuccess,
        failed: notifyPaymentFailed
    },
    review: {
        submitted: notifyReviewSubmitted
    },
    address: {
        added: notifyAddressAdded,
        updated: notifyAddressUpdated
    }
};
