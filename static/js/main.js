// Daily Fitness - Main JavaScript File

$(document).ready(function() {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Initialize popovers
    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    var popoverList = popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });

    // Update cart count
    updateCartCount();

    // Auto-hide alerts after 5 seconds
    setTimeout(function() {
        $('.alert').fadeOut();
    }, 5000);

    // Smooth scrolling for anchor links
    $('a[href^="#"]').on('click', function(event) {
        var target = $(this.getAttribute('href'));
        if (target.length) {
            event.preventDefault();
            $('html, body').stop().animate({
                scrollTop: target.offset().top - 80
            }, 1000);
        }
    });

    // Form validation
    $('.needs-validation').on('submit', function(event) {
        if (this.checkValidity() === false) {
            event.preventDefault();
            event.stopPropagation();
        }
        $(this).addClass('was-validated');
    });

    // Image lazy loading
    if ('IntersectionObserver' in window) {
        const imageObserver = new IntersectionObserver((entries, observer) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    img.src = img.dataset.src;
                    img.classList.remove('lazy');
                    imageObserver.unobserve(img);
                }
            });
        });

        document.querySelectorAll('img[data-src]').forEach(img => {
            imageObserver.observe(img);
        });
    }
});

// Update cart count function
function updateCartCount() {
    $.ajax({
        url: '/api/cart_count',
        method: 'GET',
        success: function(response) {
            $('#cart-count').text(response.count);
            if (response.count > 0) {
                $('#cart-count').show();
            } else {
                $('#cart-count').hide();
            }
        },
        error: function() {
            console.log('Error updating cart count');
        }
    });
}

// Show notification function
function showNotification(message, type = 'info') {
    const alertClass = type === 'error' ? 'alert-danger' : 
                      type === 'success' ? 'alert-success' : 
                      type === 'warning' ? 'alert-warning' : 'alert-info';
    
    const notification = $(`
        <div class="alert ${alertClass} alert-dismissible fade show position-fixed" 
             style="top: 20px; right: 20px; z-index: 9999; min-width: 300px;">
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `);
    
    $('body').append(notification);
    
    // Auto-hide after 3 seconds
    setTimeout(function() {
        notification.fadeOut(function() {
            $(this).remove();
        });
    }, 3000);
}

// Add to cart function
function addToCart(productId, quantity = 1) {
    $.ajax({
        url: '/api/add_to_cart',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            product_id: productId,
            quantity: quantity
        }),
        success: function(response) {
            if (response.success) {
                updateCartCount();
                showNotification('Product added to cart!', 'success');
            } else {
                showNotification(response.message, 'error');
            }
        },
        error: function() {
            showNotification('Error adding product to cart', 'error');
        }
    });
}

// Update cart item quantity
function updateCartItem(productId, quantity) {
    $.ajax({
        url: '/api/update_cart',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            product_id: productId,
            quantity: quantity
        }),
        success: function(response) {
            if (response.success) {
                updateCartCount();
                showNotification('Cart updated!', 'success');
            } else {
                showNotification(response.message, 'error');
            }
        },
        error: function() {
            showNotification('Error updating cart', 'error');
        }
    });
}

// Remove from cart function
function removeFromCart(productId) {
    if (confirm('Are you sure you want to remove this item from your cart?')) {
        $.ajax({
            url: '/api/remove_from_cart',
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({
                product_id: productId
            }),
            success: function(response) {
                if (response.success) {
                    updateCartCount();
                    showNotification('Product removed from cart', 'success');
                    // Remove the item from the DOM
                    $(`[data-product-id="${productId}"]`).closest('.cart-item').fadeOut();
                }
            },
            error: function() {
                showNotification('Error removing product from cart', 'error');
            }
        });
    }
}

// Search functionality
function performSearch(query) {
    if (query.length > 2) {
        $.ajax({
            url: '/api/search',
            method: 'GET',
            data: { q: query },
            success: function(response) {
                displaySearchResults(response.results);
            }
        });
    }
}

// Display search results
function displaySearchResults(results) {
    const searchResults = $('#search-results');
    searchResults.empty();
    
    if (results.length > 0) {
        results.forEach(product => {
            const resultItem = $(`
                <div class="search-result-item">
                    <a href="/product/${product.id}">
                        <img src="${product.image_url || '/static/images/placeholder.jpg'}" alt="${product.name}">
                        <div class="result-info">
                            <h6>${product.name}</h6>
                            <p class="text-muted">${product.category}</p>
                            <span class="price">$${product.price}</span>
                        </div>
                    </a>
                </div>
            `);
            searchResults.append(resultItem);
        });
    } else {
        searchResults.append('<p class="text-muted">No products found</p>');
    }
}

// Product image zoom
function initImageZoom() {
    $('.product-image img').on('click', function() {
        const src = $(this).attr('src');
        const modal = $(`
            <div class="modal fade" id="imageModal" tabindex="-1">
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-body text-center">
                            <img src="${src}" class="img-fluid">
                        </div>
                    </div>
                </div>
            </div>
        `);
        
        $('body').append(modal);
        modal.modal('show');
        
        modal.on('hidden.bs.modal', function() {
            modal.remove();
        });
    });
}

// Form auto-save functionality
function initAutoSave() {
    $('.auto-save').on('input change', function() {
        const form = $(this).closest('form');
        const formData = form.serialize();
        
        clearTimeout(form.data('timeout'));
        form.data('timeout', setTimeout(function() {
            $.ajax({
                url: form.attr('action'),
                method: 'POST',
                data: formData,
                success: function() {
                    showNotification('Changes saved automatically', 'success');
                }
            });
        }, 2000));
    });
}

// Price range slider
function initPriceRangeSlider() {
    const slider = document.getElementById('priceRange');
    if (slider) {
        const output = document.getElementById('priceOutput');
        output.innerHTML = '$' + slider.value;
        
        slider.oninput = function() {
            output.innerHTML = '$' + this.value;
        };
    }
}

// Category filter
function filterByCategory(category) {
    const url = new URL(window.location);
    if (category === 'all') {
        url.searchParams.delete('category');
    } else {
        url.searchParams.set('category', category);
    }
    window.location.href = url.toString();
}

// Sort functionality
function sortProducts(sortBy) {
    const url = new URL(window.location);
    url.searchParams.set('sort', sortBy);
    window.location.href = url.toString();
}

// Wishlist functionality
function toggleWishlist(productId) {
    $.ajax({
        url: '/api/toggle_wishlist',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            product_id: productId
        }),
        success: function(response) {
            if (response.success) {
                const button = $(`[data-product-id="${productId}"]`);
                const icon = button.find('i');
                
                if (response.in_wishlist) {
                    icon.removeClass('far').addClass('fas');
                    showNotification('Added to wishlist', 'success');
                } else {
                    icon.removeClass('fas').addClass('far');
                    showNotification('Removed from wishlist', 'info');
                }
            }
        }
    });
}

// Product comparison
function addToComparison(productId) {
    // Implementation for product comparison feature
    console.log('Adding product to comparison:', productId);
}

// Share product
function shareProduct(productId, productName) {
    if (navigator.share) {
        navigator.share({
            title: productName,
            text: 'Check out this gym equipment!',
            url: window.location.href
        });
    } else {
        // Fallback for browsers that don't support Web Share API
        const url = window.location.href;
        navigator.clipboard.writeText(url).then(function() {
            showNotification('Product link copied to clipboard!', 'success');
        });
    }
}

// Initialize all functions when document is ready
$(document).ready(function() {
    initImageZoom();
    initAutoSave();
    initPriceRangeSlider();
    
    // Mobile menu toggle
    $('.navbar-toggler').on('click', function() {
        $('.navbar-collapse').toggleClass('show');
    });
    
    // Close mobile menu when clicking on a link
    $('.navbar-nav .nav-link').on('click', function() {
        $('.navbar-collapse').removeClass('show');
    });
    
    // Back to top button
    $(window).scroll(function() {
        if ($(this).scrollTop() > 100) {
            $('.back-to-top').fadeIn();
        } else {
            $('.back-to-top').fadeOut();
        }
    });
    
    $('.back-to-top').click(function() {
        $('html, body').animate({scrollTop: 0}, 800);
        return false;
    });
    
    // Product card hover effects
    $('.product-card').hover(
        function() {
            $(this).find('.product-overlay').fadeIn();
        },
        function() {
            $(this).find('.product-overlay').fadeOut();
        }
    );
    
    // Form submission with loading state
    $('form').on('submit', function() {
        const submitBtn = $(this).find('button[type="submit"]');
        const originalText = submitBtn.text();
        
        submitBtn.prop('disabled', true)
                .html('<i class="fas fa-spinner fa-spin me-2"></i>Processing...');
        
        // Re-enable button after 5 seconds as fallback
        setTimeout(function() {
            submitBtn.prop('disabled', false).text(originalText);
        }, 5000);
    });
    
    // Input formatting
    $('input[type="tel"]').on('input', function() {
        let value = this.value.replace(/\D/g, '');
        if (value.length >= 10) {
            value = value.replace(/(\d{3})(\d{3})(\d{4})/, '($1) $2-$3');
        }
        this.value = value;
    });
    
    // Currency formatting
    $('input[type="number"][data-currency]').on('blur', function() {
        const value = parseFloat(this.value);
        if (!isNaN(value)) {
            this.value = value.toFixed(2);
        }
    });
});

// Utility functions
function formatCurrency(amount) {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD'
    }).format(amount);
}

function formatDate(date) {
    return new Date(date).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    });
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Export functions for use in other scripts
window.GymStore = {
    updateCartCount,
    showNotification,
    addToCart,
    updateCartItem,
    removeFromCart,
    toggleWishlist,
    formatCurrency,
    formatDate,
    debounce
};
