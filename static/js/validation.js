/**
 * Gym Store - Validation & Alert System
 * Provides reusable validation functions and SweetAlert2 wrappers
 */

// ==================== SWEETALERT2 WRAPPERS ====================

/**
 * Show success alert (Minimalist)
 * @param {string} title - Alert title
 * @param {string} text - Alert message (optional)
 */
function showSuccess(title, text = '') {
    Swal.fire({
        icon: 'success',
        title: title,
        text: text,
        confirmButtonColor: '#000',
        confirmButtonText: 'OK',
        timer: 2500,
        timerProgressBar: true,
        showClass: {
            popup: 'swal2-noanimation'
        },
        hideClass: {
            popup: ''
        },
        customClass: {
            popup: 'minimalist-popup',
            title: 'minimalist-title',
            confirmButton: 'minimalist-button'
        }
    });
}

/**
 * Show error alert (Minimalist)
 * @param {string} title - Alert title
 * @param {string} text - Alert message (optional)
 */
function showError(title, text = '') {
    Swal.fire({
        icon: 'error',
        title: title,
        text: text,
        confirmButtonColor: '#000',
        confirmButtonText: 'OK',
        showClass: {
            popup: 'swal2-noanimation'
        },
        hideClass: {
            popup: ''
        },
        customClass: {
            popup: 'minimalist-popup',
            title: 'minimalist-title',
            confirmButton: 'minimalist-button'
        }
    });
}

/**
 * Show warning alert (Minimalist)
 * @param {string} title - Alert title
 * @param {string} text - Alert message (optional)
 */
function showWarning(title, text = '') {
    Swal.fire({
        icon: 'warning',
        title: title,
        text: text,
        confirmButtonColor: '#000',
        confirmButtonText: 'OK',
        showClass: {
            popup: 'swal2-noanimation'
        },
        hideClass: {
            popup: ''
        },
        customClass: {
            popup: 'minimalist-popup',
            title: 'minimalist-title',
            confirmButton: 'minimalist-button'
        }
    });
}

/**
 * Show info alert (Minimalist)
 * @param {string} title - Alert title
 * @param {string} text - Alert message (optional)
 */
function showInfo(title, text = '') {
    Swal.fire({
        icon: 'info',
        title: title,
        text: text,
        confirmButtonColor: '#000',
        confirmButtonText: 'OK',
        showClass: {
            popup: 'swal2-noanimation'
        },
        hideClass: {
            popup: ''
        },
        customClass: {
            popup: 'minimalist-popup',
            title: 'minimalist-title',
            confirmButton: 'minimalist-button'
        }
    });
}

/**
 * Show toast notification (Minimalist - small popup at corner)
 * @param {string} icon - 'success', 'error', 'warning', 'info'
 * @param {string} title - Toast message
 * @param {string} position - Toast position (default: 'top-end')
 */
function showToast(icon, title, position = 'top-end') {
    const Toast = Swal.mixin({
        toast: true,
        position: position,
        showConfirmButton: false,
        timer: 2500,
        timerProgressBar: false,
        showClass: {
            popup: 'swal2-noanimation'
        },
        hideClass: {
            popup: ''
        },
        customClass: {
            popup: 'minimalist-toast',
            title: 'minimalist-toast-title'
        },
        didOpen: (toast) => {
            toast.addEventListener('mouseenter', Swal.stopTimer);
            toast.addEventListener('mouseleave', Swal.resumeTimer);
        }
    });

    Toast.fire({
        icon: icon,
        title: title
    });
}

/**
 * Show confirmation dialog (Minimalist)
 * @param {string} title - Dialog title
 * @param {string} text - Dialog message
 * @param {string} confirmText - Confirm button text (default: 'Yes')
 * @param {string} cancelText - Cancel button text (default: 'No')
 * @returns {Promise<boolean>} - True if confirmed, false if cancelled
 */
async function showConfirm(title, text, confirmText = 'Yes', cancelText = 'No') {
    const result = await Swal.fire({
        title: title,
        text: text,
        icon: 'question',
        showCancelButton: true,
        confirmButtonColor: '#000',
        cancelButtonColor: '#999',
        confirmButtonText: confirmText,
        cancelButtonText: cancelText,
        showClass: {
            popup: 'swal2-noanimation'
        },
        hideClass: {
            popup: ''
        },
        customClass: {
            popup: 'minimalist-popup',
            title: 'minimalist-title',
            confirmButton: 'minimalist-button',
            cancelButton: 'minimalist-button-cancel'
        }
    });
    return result.isConfirmed;
}

/**
 * Show loading spinner (Minimalist)
 * @param {string} title - Loading message
 */
function showLoading(title = 'Please wait...') {
    Swal.fire({
        title: title,
        allowOutsideClick: false,
        allowEscapeKey: false,
        showConfirmButton: false,
        showClass: {
            popup: 'swal2-noanimation'
        },
        hideClass: {
            popup: ''
        },
        customClass: {
            popup: 'minimalist-popup minimalist-loading',
            title: 'minimalist-title'
        },
        didOpen: () => {
            Swal.showLoading();
        }
    });
}

/**
 * Close any open SweetAlert
 */
function closeAlert() {
    Swal.close();
}

// ==================== VALIDATION FUNCTIONS ====================

/**
 * Validate email format
 * @param {string} email - Email to validate
 * @returns {boolean} - True if valid
 */
function isValidEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
}

/**
 * Validate password strength
 * @param {string} password - Password to validate
 * @returns {object} - {isValid: boolean, strength: string, message: string}
 */
function validatePassword(password) {
    const minLength = 8;
    const hasUpperCase = /[A-Z]/.test(password);
    const hasLowerCase = /[a-z]/.test(password);
    const hasNumbers = /\d/.test(password);
    const hasSpecialChar = /[!@#$%^&*(),.?":{}|<>]/.test(password);

    let strength = 0;
    let message = '';

    if (password.length < minLength) {
        return {
            isValid: false,
            strength: 'weak',
            message: `Password must be at least ${minLength} characters long`
        };
    }

    if (hasUpperCase) strength++;
    if (hasLowerCase) strength++;
    if (hasNumbers) strength++;
    if (hasSpecialChar) strength++;

    if (strength === 4) {
        return { isValid: true, strength: 'strong', message: 'Strong password' };
    } else if (strength === 3) {
        return { isValid: true, strength: 'good', message: 'Good password' };
    } else if (strength === 2) {
        return { isValid: true, strength: 'fair', message: 'Fair password' };
    } else {
        return { isValid: false, strength: 'weak', message: 'Password is too weak' };
    }
}

/**
 * Check if passwords match
 * @param {string} password - Password
 * @param {string} confirmPassword - Confirm password
 * @returns {boolean} - True if passwords match
 */
function passwordsMatch(password, confirmPassword) {
    return password === confirmPassword;
}

/**
 * Validate phone number (Philippine format)
 * @param {string} phone - Phone number to validate
 * @returns {boolean} - True if valid
 */
function isValidPhone(phone) {
    if (!phone) return false;

    // Normalize: remove spaces, hyphens, dots and parentheses
    const cleaned = phone.replace(/[\s\-\.\(\)]/g, '');

    /*
     Acceptable formats now:
     - Local with leading 0: 09XXXXXXXXX (e.g. 09171234567)
     - International with plus: +639XXXXXXXXX (e.g. +639171234567)
     - International without plus: 639XXXXXXXXX (e.g. 639171234567)
     - Short mobile (no leading 0): 9XXXXXXXXX (e.g. 9171234567)
    */
    const patterns = [
        /^09\d{9}$/,     // 0917xxxxxxx
        /^\+639\d{9}$/, // +63917xxxxxxx
        /^639\d{9}$/,    // 63917xxxxxxx
        /^9\d{9}$/       // 917xxxxxxx
    ];

    return patterns.some((rx) => rx.test(cleaned));
}

/**
 * Format a cleaned phone number into a human-friendly Philippine format.
 * Accepts partial input and returns a best-effort formatted string.
 * Examples:
 *  - 09171234567 -> 0917 123 4567
 *  - +639171234567 -> +63 917 123 4567
 *  - 639171234567 -> +63 917 123 4567
 *  - 9171234567 -> 917 123 4567
 */
function formatPhoneNumber(input) {
    if (!input) return '';

    // preserve leading + if present for international format
    let value = input.trim();
    let hasPlus = value.startsWith('+');

    // remove everything except digits
    const digits = value.replace(/[^0-9]/g, '');
    if (digits.length === 0) return value;

    // helper to chunk safely
    const chunk = (s, start, len) => s.substring(start, Math.min(start + len, s.length));

    // International starting with country code 63
    if ((hasPlus && digits.startsWith('63')) || digits.startsWith('63')) {
        // digits after country code
        const after = digits.substring(2);
        const p1 = chunk(after, 0, 3);
        const p2 = chunk(after, 3, 3);
        const p3 = chunk(after, 6, 4);
        let out = '+63';
        if (p1) out += ' ' + p1;
        if (p2) out += ' ' + p2;
        if (p3) out += ' ' + p3;
        return out;
    }

    // Local starting with 0 e.g., 0917xxxxxxx (11 digits)
    if (digits.startsWith('0')) {
        // common mobile is 11 digits: 4-3-4
        const p1 = chunk(digits, 0, 4);
        const p2 = chunk(digits, 4, 3);
        const p3 = chunk(digits, 7, 4);
        let out = p1;
        if (p2) out += ' ' + p2;
        if (p3) out += ' ' + p3;
        return out;
    }

    // Short mobile without leading 0 e.g., 9171234567 (10 digits)
    if (digits.startsWith('9')) {
        const p1 = chunk(digits, 0, 3);
        const p2 = chunk(digits, 3, 3);
        const p3 = chunk(digits, 6, 4);
        let out = p1;
        if (p2) out += ' ' + p2;
        if (p3) out += ' ' + p3;
        return out;
    }

    // Fallback: group by 3s then leftover
    let groups = [];
    for (let i = 0; i < digits.length; i += 3) {
        groups.push(digits.substring(i, i + 3));
    }
    return groups.join(' ');
}

/**
 * Attach a formatter to an input element (by element or id).
 * Looks for inputs with class 'phone-format' automatically on DOMContentLoaded.
 */
function addPhoneFormatter(input) {
    let el = null;
    if (typeof input === 'string') el = document.getElementById(input) || document.querySelector(input);
    else el = input;
    if (!el) return;

    // On input, preserve a basic caret position heuristic
    el.addEventListener('input', (e) => {
        const start = el.selectionStart;
        const raw = el.value;
        const formatted = formatPhoneNumber(raw);
        el.value = formatted;

        // try to restore caret near the end of inserted text
        try {
            const pos = Math.min(formatted.length, start + (formatted.length - raw.length));
            el.setSelectionRange(pos, pos);
        } catch (err) {
            // ignore selection errors
        }
    });

    // On blur, normalize to a cleaned format (optional: you can change behavior)
    el.addEventListener('blur', () => {
        // keep formatted display, optionally could store cleaned value to hidden input
        el.value = formatPhoneNumber(el.value);
    });
}

// auto-attach to inputs with class 'phone-format' when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    const inputs = document.querySelectorAll('input.phone-format');
    inputs.forEach(i => addPhoneFormatter(i));
});

/**
 * Check if required fields are filled
 * @param {HTMLFormElement} form - Form element
 * @returns {object} - {isValid: boolean, emptyFields: array}
 */
function checkRequiredFields(form) {
    const requiredFields = form.querySelectorAll('[required]');
    const emptyFields = [];

    requiredFields.forEach(field => {
        if (!field.value.trim()) {
            emptyFields.push(field.name || field.id);
        }
    });

    return {
        isValid: emptyFields.length === 0,
        emptyFields: emptyFields
    };
}

/**
 * Validate file upload
 * @param {File} file - File to validate
 * @param {array} allowedTypes - Allowed file types (e.g., ['image/jpeg', 'image/png'])
 * @param {number} maxSizeMB - Maximum file size in MB
 * @returns {object} - {isValid: boolean, message: string}
 */
function validateFile(file, allowedTypes, maxSizeMB) {
    if (!file) {
        return { isValid: false, message: 'No file selected' };
    }

    if (!allowedTypes.includes(file.type)) {
        return { isValid: false, message: 'Invalid file type' };
    }

    const maxSizeBytes = maxSizeMB * 1024 * 1024;
    if (file.size > maxSizeBytes) {
        return { isValid: false, message: `File size must be less than ${maxSizeMB}MB` };
    }

    return { isValid: true, message: 'File is valid' };
}

/**
 * Validate number range
 * @param {number} value - Value to validate
 * @param {number} min - Minimum value
 * @param {number} max - Maximum value
 * @returns {boolean} - True if valid
 */
function isInRange(value, min, max) {
    return value >= min && value <= max;
}

/**
 * Add real-time password match indicator
 * @param {string} passwordId - Password field ID
 * @param {string} confirmPasswordId - Confirm password field ID
 * @param {string} indicatorId - Indicator element ID (optional)
 */
function addPasswordMatchIndicator(passwordId, confirmPasswordId, indicatorId = null) {
    const passwordField = document.getElementById(passwordId);
    const confirmPasswordField = document.getElementById(confirmPasswordId);

    if (!passwordField || !confirmPasswordField) return;

    // Create indicator if not provided
    let indicator;
    if (indicatorId) {
        indicator = document.getElementById(indicatorId);
    } else {
        indicator = document.createElement('small');
        indicator.className = 'form-text';
        indicator.id = 'password-match-indicator';
        confirmPasswordField.parentElement.appendChild(indicator);
    }

    const checkMatch = () => {
        const password = passwordField.value;
        const confirmPassword = confirmPasswordField.value;

        if (confirmPassword === '') {
            indicator.textContent = '';
            indicator.className = 'form-text';
            return;
        }

        if (password === confirmPassword) {
            indicator.innerHTML = '<i class="fas fa-check-circle text-success"></i> Passwords match';
            indicator.className = 'form-text text-success';
        } else {
            indicator.innerHTML = '<i class="fas fa-times-circle text-danger"></i> Passwords do not match';
            indicator.className = 'form-text text-danger';
        }
    };

    passwordField.addEventListener('input', checkMatch);
    confirmPasswordField.addEventListener('input', checkMatch);
}

/**
 * Add real-time password strength indicator
 * @param {string} passwordId - Password field ID
 * @param {string} indicatorId - Indicator element ID (optional)
 */
function addPasswordStrengthIndicator(passwordId, indicatorId = null) {
    const passwordField = document.getElementById(passwordId);
    if (!passwordField) return;

    // Create indicator if not provided
    let indicator;
    if (indicatorId) {
        indicator = document.getElementById(indicatorId);
    } else {
        indicator = document.createElement('div');
        indicator.id = 'password-strength-indicator';
        indicator.className = 'mt-1';
        indicator.style.cssText = 'font-size: 0.75rem;';
        
        // Insert after the parent element (below the password field)
        const parent = passwordField.parentElement;
        if (parent.nextSibling) {
            parent.parentNode.insertBefore(indicator, parent.nextSibling);
        } else {
            parent.parentNode.appendChild(indicator);
        }
    }

    passwordField.addEventListener('input', () => {
        const password = passwordField.value;
        
        if (password === '') {
            indicator.innerHTML = '';
            return;
        }

        const result = validatePassword(password);
        let color = '';
        let progressWidth = 0;

        switch (result.strength) {
            case 'weak':
                color = '#dc3545';
                progressWidth = 25;
                break;
            case 'fair':
                color = '#ffc107';
                progressWidth = 50;
                break;
            case 'good':
                color = '#17a2b8';
                progressWidth = 75;
                break;
            case 'strong':
                color = '#28a745';
                progressWidth = 100;
                break;
        }

        indicator.innerHTML = `
            <div style="display: flex; align-items: center; gap: 8px;">
                <span style="color: #6c757d; font-size: 0.75rem; white-space: nowrap;">${result.strength.toUpperCase()}</span>
                <div style="flex: 1; height: 3px; background: #e9ecef; border-radius: 2px; overflow: hidden;">
                    <div style="width: ${progressWidth}%; height: 100%; background: ${color}; transition: width 0.3s ease;"></div>
                </div>
            </div>
        `;
    });
}

// ==================== FORM SUBMISSION HELPERS ====================

/**
 * Handle form submission with validation and loading state
 * @param {HTMLFormElement} form - Form element
 * @param {function} validationCallback - Custom validation function (returns {isValid: boolean, message: string})
 * @param {string} loadingMessage - Loading message (default: 'Processing...')
 */
async function handleFormSubmit(form, validationCallback = null, loadingMessage = 'Processing...') {
    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        // Check required fields
        const requiredCheck = checkRequiredFields(form);
        if (!requiredCheck.isValid) {
            showWarning('Please complete all required fields', 
                `Missing fields: ${requiredCheck.emptyFields.join(', ')}`);
            return;
        }

        // Run custom validation if provided
        if (validationCallback) {
            const validationResult = validationCallback();
            if (!validationResult.isValid) {
                showWarning('Validation Error', validationResult.message);
                return;
            }
        }

        // Show loading
        showLoading(loadingMessage);

        // Submit form
        try {
            form.submit();
        } catch (error) {
            closeAlert();
            showError('Submission Error', 'An error occurred. Please try again.');
        }
    });
}

// ==================== EXPORT FOR USE ====================
// Make functions globally available
window.ValidationUtils = {
    // Alerts
    showSuccess,
    showError,
    showWarning,
    showInfo,
    showToast,
    showConfirm,
    showLoading,
    closeAlert,
    
    // Validation
    isValidEmail,
    validatePassword,
    passwordsMatch,
    isValidPhone,
    checkRequiredFields,
    validateFile,
    isInRange,
    
    // Helpers
    addPasswordMatchIndicator,
    addPasswordStrengthIndicator,
    handleFormSubmit
};
