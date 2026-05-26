/**
 * Smart Search System for Gym Store
 * Features: Search history, auto-suggestions, trending searches, smart recommendations
 */

class SmartSearch {
    constructor(inputId, dropdownId) {
        this.input = document.getElementById(inputId);
        this.dropdown = document.getElementById(dropdownId);
        this.searchTimeout = null;
        this.cache = new Map();
        this.isOpen = false;
        
        if (!this.input || !this.dropdown) {
            console.error('Smart Search: Input or dropdown element not found');
            return;
        }
        
        this.init();
    }
    
    init() {
        // Event listeners
        this.input.addEventListener('focus', () => this.onFocus());
        this.input.addEventListener('input', (e) => this.onInput(e));
        this.input.addEventListener('keydown', (e) => this.onKeyDown(e));
        
        // Close dropdown when clicking outside
        document.addEventListener('click', (e) => {
            if (!this.input.contains(e.target) && !this.dropdown.contains(e.target)) {
                this.close();
            }
        });
        
        // Handle form submission
        const form = this.input.closest('form');
        if (form) {
            form.addEventListener('submit', (e) => {
                const query = this.input.value.trim();
                
                if (this.isOpen) {
                    // If dropdown is open, select first result instead of submitting
                    e.preventDefault();
                    this.selectFirstResult();
                } else if (query.length > 0) {
                    // Save to history when actually submitting the form
                    this.saveSearch(query, 0);
                }
            });
        }
    }
    
    async onFocus() {
        const query = this.input.value.trim();
        
        if (query.length === 0) {
            // Show simple category suggestions when clicking on empty search bar
            await this.showCategorySuggestions();
        } else if (query.length >= 1) {
            // Show search results if already typing (even with 1 character)
            await this.search(query);
        }
    }
    
    onInput(e) {
        const query = e.target.value.trim();
        
        // Clear previous timeout
        if (this.searchTimeout) {
            clearTimeout(this.searchTimeout);
        }
        
        if (query.length === 0) {
            // Show category suggestions when input is cleared
            this.showCategorySuggestions();
            return;
        }
        
        // Search immediately with 1 or more characters
        if (query.length >= 1) {
            // Debounce search
            this.searchTimeout = setTimeout(() => {
                this.search(query);
            }, 300);
        }
    }
    
    onKeyDown(e) {
        if (!this.isOpen) return;
        
        const items = this.dropdown.querySelectorAll('.search-result-item');
        const activeItem = this.dropdown.querySelector('.search-result-item.active');
        let currentIndex = Array.from(items).indexOf(activeItem);
        
        switch(e.key) {
            case 'ArrowDown':
                e.preventDefault();
                currentIndex = (currentIndex + 1) % items.length;
                this.setActiveItem(items[currentIndex]);
                break;
                
            case 'ArrowUp':
                e.preventDefault();
                currentIndex = currentIndex <= 0 ? items.length - 1 : currentIndex - 1;
                this.setActiveItem(items[currentIndex]);
                break;
                
            case 'Enter':
                e.preventDefault();
                if (activeItem) {
                    activeItem.click();
                } else {
                    this.selectFirstResult();
                }
                break;
                
            case 'Escape':
                this.close();
                break;
        }
    }
    
    setActiveItem(item) {
        // Remove active class from all items
        this.dropdown.querySelectorAll('.search-result-item').forEach(el => {
            el.classList.remove('active');
        });
        
        // Add active class to selected item
        if (item) {
            item.classList.add('active');
            item.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        }
    }
    
    selectFirstResult() {
        const firstItem = this.dropdown.querySelector('.search-result-item');
        if (firstItem) {
            firstItem.click();
        }
    }
    
    async showCategorySuggestions() {
        try {
            const response = await fetch('/api/search/categories');
            const data = await response.json();
            
            if (!data.categories || data.categories.length === 0) {
                this.close();
                return;
            }
            
            let html = '<div class="search-section" style="padding: 12px 0;">';
            html += '<div class="search-section-header" style="padding: 8px 16px; background: #f8f9fa; border-bottom: 1px solid #e0e0e0;">';
            html += '<span style="display: flex; align-items: center; gap: 8px; font-size: 13px; font-weight: 600; color: #666;"><i class="fas fa-lightbulb" style="color: #ffc107;"></i>Recommended</span>';
            html += '</div>';
            
            data.categories.forEach(category => {
                const productCount = category.product_count || 0;
                html += `
                    <a href="/buyer/shop?category=${encodeURIComponent(category.name)}" class="search-result-item category-item" style="display: flex; align-items: center; padding: 12px 16px; text-decoration: none; color: #333; border-bottom: 1px solid #f5f5f5; transition: background 0.2s;">
                        <i class="fas fa-lightbulb" style="color: #ffc107; font-size: 18px; margin-right: 12px; width: 24px; text-align: center;"></i>
                        <div style="flex: 1;">
                            <div style="font-size: 15px; font-weight: 500; color: #333; margin-bottom: 2px;">${this.escapeHtml(category.name)}</div>
                            <small style="color: #999; font-size: 12px;">${productCount} products available</small>
                        </div>
                    </a>
                `;
            });
            
            html += '</div>';
            
            this.dropdown.innerHTML = html;
            this.open();
            
            // Add hover effects
            this.dropdown.querySelectorAll('.search-result-item').forEach(item => {
                item.addEventListener('mouseenter', function() {
                    this.style.background = '#f8f9fa';
                });
                item.addEventListener('mouseleave', function() {
                    this.style.background = 'white';
                });
            });
            
        } catch (error) {
            console.error('Error loading category suggestions:', error);
            this.close();
        }
    }
    
    async showInitialSuggestions() {
        // Just show categories now
        await this.showCategorySuggestions();
    }
    
    async search(query, saveToHistory = false) {
        // Check cache first
        if (this.cache.has(query)) {
            this.displayResults(this.cache.get(query), query);
            return;
        }
        
        try {
            const response = await fetch(`/api/search/autocomplete?q=${encodeURIComponent(query)}`);
            const data = await response.json();
            
            // Cache results
            this.cache.set(query, data);
            
            // Only save search to history if explicitly requested (on submit/click)
            if (saveToHistory) {
                this.saveSearch(query, data.suggestions ? data.suggestions.length : 0);
            }
            
            this.displayResults(data, query);
            
        } catch (error) {
            console.error('Search error:', error);
            this.close();
        }
    }
    
    displayResults(data, query) {
        if (!data.suggestions || data.suggestions.length === 0) {
            this.dropdown.innerHTML = `
                <div class="search-no-results">
                    <i class="fas fa-search mb-2"></i>
                    <p>No results found for "${query}"</p>
                    <small class="text-muted">Try different keywords</small>
                </div>
            `;
            this.open();
            return;
        }
        
        let html = '';
        
        // Group by type
        const products = data.suggestions.filter(s => s.type === 'product');
        const categories = data.suggestions.filter(s => s.type === 'category');
        
        // Products
        if (products.length > 0) {
            html += '<div class="search-section">';
            html += '<div class="search-section-header"><span>Products</span></div>';
            
            products.forEach(product => {
                html += this.renderProductItem(product, query);
            });
            
            html += '</div>';
        }
        
        // Categories
        if (categories.length > 0) {
            html += '<div class="search-section">';
            html += '<div class="search-section-header"><span>Categories</span></div>';
            
            categories.forEach(category => {
                html += this.renderCategoryItem(category, query);
            });
            
            html += '</div>';
        }
        
        this.dropdown.innerHTML = html;
        this.open();
    }
    
    renderProductItem(product, query) {
        const highlightedName = this.highlightMatch(product.name, query);
        const image = product.image_url || '/static/images/placeholder.png';
        const escapedQuery = this.escapeHtml(query);
        
        return `
            <a href="${product.url}" class="search-result-item product-item" onclick="smartSearch.saveSearchOnClick('${escapedQuery}')" style="display: flex; align-items: center; padding: 12px 16px; text-decoration: none; color: #333; border-bottom: 1px solid #f5f5f5; gap: 12px; transition: background 0.2s;">
                <img src="${image}" alt="${product.name}" loading="lazy" onerror="this.src='/static/images/placeholder.png'" style="width: 60px; height: 60px; object-fit: cover; border-radius: 6px; border: 1px solid #e8e8e8; flex-shrink: 0; display: block;">
                <div style="flex: 1; min-width: 0;">
                    <div style="font-size: 14px; font-weight: 500; color: #333; margin-bottom: 4px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${highlightedName}</div>
                    <div style="display: flex; gap: 8px; font-size: 12px; color: #999; margin-bottom: 4px;">
                        ${product.brand ? `<span style="font-weight: 500; color: #666;">${product.brand}</span>` : ''}
                        <span style="color: #999;">${product.category}</span>
                    </div>
                    <div style="font-size: 14px; font-weight: 600; color: #ee4d2d;">₱${product.price.toFixed(2)}</div>
                </div>
            </a>
        `;
    }
    
    renderCategoryItem(category, query) {
        const highlightedName = this.highlightMatch(category.name, query);
        
        return `
            <a href="${category.url}" class="search-result-item category-item">
                <i class="fas fa-folder me-2"></i>
                <span>${highlightedName}</span>
                <i class="fas fa-arrow-right ms-auto"></i>
            </a>
        `;
    }
    
    renderHistoryItem(query) {
        return `
            <div class="search-result-item history-item" onclick="smartSearch.selectQuery('${this.escapeHtml(query)}')">
                <i class="fas fa-history me-2"></i>
                <span>${this.escapeHtml(query)}</span>
            </div>
        `;
    }
    
    renderTrendingItem(query, count) {
        return `
            <div class="search-result-item trending-item" onclick="smartSearch.selectQuery('${this.escapeHtml(query)}')">
                <i class="fas fa-fire me-2"></i>
                <span>${this.escapeHtml(query)}</span>
                <span class="badge ms-auto">${count}</span>
            </div>
        `;
    }
    
    renderRecommendationItem(query, reason) {
        return `
            <div class="search-result-item recommendation-item" onclick="smartSearch.selectQuery('${this.escapeHtml(query)}')">
                <i class="fas fa-lightbulb me-2"></i>
                <div class="flex-grow-1">
                    <div>${this.escapeHtml(query)}</div>
                    <small class="text-muted">${this.escapeHtml(reason)}</small>
                </div>
            </div>
        `;
    }
    
    highlightMatch(text, query) {
        if (!query) return this.escapeHtml(text);
        
        const regex = new RegExp(`(${this.escapeRegex(query)})`, 'gi');
        return this.escapeHtml(text).replace(regex, '<mark>$1</mark>');
    }
    
    selectQuery(query) {
        this.input.value = query;
        this.close();
        this.search(query);
    }
    
    async getSearchHistory() {
        try {
            const response = await fetch('/api/search/history');
            return await response.json();
        } catch (error) {
            console.error('Error fetching search history:', error);
            return { searches: [] };
        }
    }
    
    async getTrendingSearches() {
        try {
            const response = await fetch('/api/search/trending');
            return await response.json();
        } catch (error) {
            console.error('Error fetching trending searches:', error);
            return { trending: [] };
        }
    }
    
    async getRecommendations() {
        try {
            const response = await fetch('/api/search/recommendations');
            return await response.json();
        } catch (error) {
            console.error('Error fetching recommendations:', error);
            return { recommendations: [] };
        }
    }
    
    async saveSearch(query, resultsCount) {
        try {
            await fetch('/api/search/save', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    query: query,
                    results_count: resultsCount
                })
            });
        } catch (error) {
            console.error('Error saving search:', error);
        }
    }
    
    async clearHistory() {
        try {
            const response = await fetch('/api/search/history/clear', {
                method: 'POST'
            });
            const data = await response.json();
            
            if (data.success) {
                // Show success message
                if (window.ValidationUtils) {
                    window.ValidationUtils.showToast('success', 'Search history cleared');
                }
                
                // Refresh suggestions
                this.showInitialSuggestions();
            }
        } catch (error) {
            console.error('Error clearing history:', error);
        }
    }
    
    open() {
        this.dropdown.style.display = 'block';
        this.isOpen = true;
    }
    
    close() {
        this.dropdown.style.display = 'none';
        this.isOpen = false;
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    escapeRegex(text) {
        return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }
}

// Global instance
let smartSearch;

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', function() {
    smartSearch = new SmartSearch('smart-search-input', 'search-suggestions');
});
