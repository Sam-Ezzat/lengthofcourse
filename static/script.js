// JavaScript for Folder Explorer Application

class FolderExplorer {
    constructor() {
        this.isAnalyzing = false;
        this.progressInterval = null;
        this.currentResults = null;
        
        this.initializeElements();
        this.bindEvents();
        this.loadQuickFolders();
    }
    
    initializeElements() {
        // Input elements
        this.folderPathInput = document.getElementById('folderPath');
        this.browseButton = document.getElementById('browseButton');
        this.calculateDurationsCheckbox = document.getElementById('calculateDurations');
        this.analyzeButton = document.getElementById('analyzeButton');
        this.cancelButton = document.getElementById('cancelButton');
        this.quickFoldersContainer = document.getElementById('quickFolders');
        
        // Section elements
        this.progressSection = document.getElementById('progressSection');
        this.resultsSection = document.getElementById('resultsSection');
        this.errorSection = document.getElementById('errorSection');
        
        // Progress elements
        this.progressFill = document.getElementById('progressFill');
        this.progressText = document.getElementById('progressText');
        this.progressPercent = document.getElementById('progressPercent');
        
        // Results elements
        this.totalFilesElement = document.getElementById('totalFiles');
        this.totalSizeElement = document.getElementById('totalSize');
        this.videoDurationElement = document.getElementById('videoDuration');
        this.audioDurationElement = document.getElementById('audioDuration');
        this.fileTypesChart = document.getElementById('fileTypesChart');
        this.detailedResults = document.getElementById('detailedResults');
        this.rawDataContent = document.getElementById('rawDataContent');
        
        // Button elements
        this.exportButton = document.getElementById('exportButton');
        this.toggleRawDataButton = document.getElementById('toggleRawData');
        this.retryButton = document.getElementById('retryButton');
        
        // Error elements
        this.errorMessage = document.getElementById('errorMessage');
    }
    
    bindEvents() {
        this.analyzeButton.addEventListener('click', () => this.startAnalysis());
        this.cancelButton.addEventListener('click', () => this.cancelAnalysis());
        this.browseButton.addEventListener('click', () => this.browseFolder());
        this.exportButton.addEventListener('click', () => this.exportResults());
        this.toggleRawDataButton.addEventListener('click', () => this.toggleRawData());
        this.retryButton.addEventListener('click', () => this.hideError());
        
        // Enter key on folder input
        this.folderPathInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !this.isAnalyzing) {
                this.startAnalysis();
            }
        });
    }
    
    async loadQuickFolders() {
        try {
            const response = await fetch('/api/sample-folders');
            const folders = await response.json();
            
            this.quickFoldersContainer.innerHTML = '';
            
            if (folders.length === 0) {
                this.quickFoldersContainer.innerHTML = '<div class="loading">No accessible folders found</div>';
                return;
            }
            
            folders.forEach(folder => {
                const folderElement = document.createElement('div');
                folderElement.className = 'quick-folder';
                folderElement.innerHTML = `
                    <span class="quick-folder-name">${folder.name}</span>
                    <span class="quick-folder-path">${folder.path}</span>
                    <span class="quick-folder-info">${folder.file_count} files</span>
                `;
                
                folderElement.addEventListener('click', () => {
                    this.folderPathInput.value = folder.path;
                });
                
                this.quickFoldersContainer.appendChild(folderElement);
            });
        } catch (error) {
            console.error('Error loading quick folders:', error);
            this.quickFoldersContainer.innerHTML = '<div class="loading">Error loading folders</div>';
        }
    }
    
    browseFolder() {
        // Note: File system access is limited in web browsers
        // This is a placeholder for a more advanced file picker
        const path = prompt('Enter folder path:');
        if (path) {
            this.folderPathInput.value = path;
        }
    }
    
    async startAnalysis() {
        const folderPath = this.folderPathInput.value.trim();
        
        if (!folderPath) {
            this.showError('Please enter a folder path');
            return;
        }
        
        this.isAnalyzing = true;
        this.updateUI();
        
        try {
            const response = await fetch('/api/analyze', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    folder_path: folderPath,
                    calculate_durations: this.calculateDurationsCheckbox.checked
                })
            });
            
            const result = await response.json();
            
            if (!response.ok) {
                throw new Error(result.error || 'Analysis failed');
            }
            
            // Start polling for progress
            this.startProgressPolling();
            
        } catch (error) {
            this.isAnalyzing = false;
            this.showError(error.message);
            this.updateUI();
        }
    }
    
    async cancelAnalysis() {
        try {
            await fetch('/api/cancel', { method: 'POST' });
            this.isAnalyzing = false;
            this.stopProgressPolling();
            this.hideAllSections();
            this.updateUI();
        } catch (error) {
            console.error('Error cancelling analysis:', error);
        }
    }
    
    startProgressPolling() {
        this.progressInterval = setInterval(async () => {
            try {
                const response = await fetch('/api/progress');
                const progress = await response.json();
                
                this.updateProgress(progress);
                
                if (progress.status === 'completed') {
                    this.stopProgressPolling();
                    this.isAnalyzing = false;
                    this.currentResults = progress.results;
                    this.showResults(progress.results);
                    this.updateUI();
                } else if (progress.status === 'error') {
                    this.stopProgressPolling();
                    this.isAnalyzing = false;
                    this.showError(progress.message);
                    this.updateUI();
                }
            } catch (error) {
                console.error('Error polling progress:', error);
                this.stopProgressPolling();
                this.isAnalyzing = false;
                this.showError('Connection error while monitoring progress');
                this.updateUI();
            }
        }, 1000);
    }
    
    stopProgressPolling() {
        if (this.progressInterval) {
            clearInterval(this.progressInterval);
            this.progressInterval = null;
        }
    }
    
    updateProgress(progress) {
        if (progress.status === 'running') {
            this.showProgress();
            this.progressFill.style.width = `${progress.progress || 0}%`;
            this.progressText.textContent = progress.message || 'Processing...';
            this.progressPercent.textContent = `${progress.progress || 0}%`;
        }
    }
    
    showProgress() {
        this.hideAllSections();
        this.progressSection.style.display = 'block';
    }
    
    showResults(results) {
        this.hideAllSections();
        this.resultsSection.style.display = 'block';
        
        // Update summary cards
        this.totalFilesElement.textContent = results.total_files.toLocaleString();
        this.totalSizeElement.textContent = results.formatted_size || this.formatSize(results.total_size);
        
        // Update media durations
        let videoDuration = 'N/A';
        let audioDuration = 'N/A';
        
        if (results.ffmpeg_available) {
            videoDuration = results.media_durations.video?.formatted_duration || '0s';
            audioDuration = results.media_durations.audio?.formatted_duration || '0s';
        } else {
            // FFmpeg not available, show file counts instead
            const videoCount = results.file_summary.video?.count || 0;
            const audioCount = results.file_summary.audio?.count || 0;
            videoDuration = videoCount > 0 ? `${videoCount} files (FFmpeg required)` : 'No video files';
            audioDuration = audioCount > 0 ? `${audioCount} files (FFmpeg required)` : 'No audio files';
        }
        
        this.videoDurationElement.textContent = videoDuration;
        this.audioDurationElement.textContent = audioDuration;
        
        // Show/hide FFmpeg warning
        const ffmpegStatus = document.getElementById('ffmpegStatus');
        if (!results.ffmpeg_available) {
            ffmpegStatus.style.display = 'block';
        } else {
            ffmpegStatus.style.display = 'none';
        }
        
        // Create file types chart
        this.createFileTypesChart(results.file_summary);
        
        // Create detailed results
        this.createDetailedResults(results.file_summary);
        
        // Update raw data
        this.rawDataContent.textContent = JSON.stringify(results, null, 2);
    }
    
    createFileTypesChart(fileSummary) {
        this.fileTypesChart.innerHTML = '';
        
        const totalFiles = Object.values(fileSummary).reduce((sum, category) => sum + category.count, 0);
        
        if (totalFiles === 0) {
            this.fileTypesChart.innerHTML = '<div class="loading">No files to display</div>';
            return;
        }
        
        // Sort categories by count
        const sortedCategories = Object.entries(fileSummary)
            .sort(([,a], [,b]) => b.count - a.count);
        
        sortedCategories.forEach(([categoryName, categoryData]) => {
            const percentage = (categoryData.count / totalFiles) * 100;
            
            const chartItem = document.createElement('div');
            chartItem.className = 'chart-item';
            chartItem.innerHTML = `
                <div class="chart-item-header">
                    <span class="chart-item-type">${categoryName}</span>
                    <span class="chart-item-count">${categoryData.count} files</span>
                </div>
                <div class="chart-item-bar">
                    <div class="chart-item-fill" style="width: ${percentage}%"></div>
                </div>
                <div class="chart-item-extensions">${categoryData.extensions.join(', ') || 'various'}</div>
            `;
            
            this.fileTypesChart.appendChild(chartItem);
        });
    }
    
    createDetailedResults(fileSummary) {
        this.detailedResults.innerHTML = '';
        
        // Sort categories by count
        const sortedCategories = Object.entries(fileSummary)
            .sort(([,a], [,b]) => b.count - a.count);
        
        sortedCategories.forEach(([categoryName, categoryData]) => {
            const categoryElement = document.createElement('div');
            categoryElement.className = 'result-category';
            
            const iconMap = {
                video: 'fas fa-video',
                audio: 'fas fa-music',
                images: 'fas fa-image',
                documents: 'fas fa-file-alt',
                code: 'fas fa-code',
                archives: 'fas fa-file-archive',
                others: 'fas fa-file'
            };
            
            const icon = iconMap[categoryName] || 'fas fa-file';
            
            categoryElement.innerHTML = `
                <h4><i class="${icon}"></i> ${categoryName} (${categoryData.count})</h4>
                <div class="result-list">
                    ${categoryData.files.slice(0, 20).map(file => 
                        `<div class="result-item">${this.getFileName(file)}</div>`
                    ).join('')}
                    ${categoryData.files.length > 20 ? 
                        `<div class="result-item"><em>... and ${categoryData.files.length - 20} more files</em></div>` : 
                        ''
                    }
                </div>
            `;
            
            this.detailedResults.appendChild(categoryElement);
        });
    }
    
    getFileName(filePath) {
        return filePath.split(/[/\\]/).pop();
    }
    
    formatSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }
    
    showError(message) {
        this.hideAllSections();
        this.errorSection.style.display = 'block';
        this.errorMessage.textContent = message;
    }
    
    hideError() {
        this.errorSection.style.display = 'none';
    }
    
    hideAllSections() {
        this.progressSection.style.display = 'none';
        this.resultsSection.style.display = 'none';
        this.errorSection.style.display = 'none';
    }
    
    updateUI() {
        // Update button states
        this.analyzeButton.disabled = this.isAnalyzing;
        this.analyzeButton.innerHTML = this.isAnalyzing ? 
            '<i class="fas fa-spinner fa-spin"></i> Analyzing...' : 
            '<i class="fas fa-play"></i> Start Analysis';
        
        this.cancelButton.style.display = this.isAnalyzing ? 'inline-flex' : 'none';
        this.folderPathInput.disabled = this.isAnalyzing;
        this.calculateDurationsCheckbox.disabled = this.isAnalyzing;
    }
    
    exportResults() {
        if (!this.currentResults) return;
        
        const dataStr = JSON.stringify(this.currentResults, null, 2);
        const dataBlob = new Blob([dataStr], { type: 'application/json' });
        const url = URL.createObjectURL(dataBlob);
        
        const link = document.createElement('a');
        link.href = url;
        link.download = `folder_analysis_${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.json`;
        link.click();
        
        URL.revokeObjectURL(url);
    }
    
    toggleRawData() {
        const isVisible = this.rawDataContent.style.display !== 'none';
        this.rawDataContent.style.display = isVisible ? 'none' : 'block';
        this.toggleRawDataButton.innerHTML = isVisible ? 
            '<i class="fas fa-eye"></i> Show' : 
            '<i class="fas fa-eye-slash"></i> Hide';
    }
}

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new FolderExplorer();
});

// Handle page visibility change to stop polling when page is hidden
document.addEventListener('visibilitychange', () => {
    if (document.hidden && window.folderExplorer) {
        // Page is hidden, could pause polling to save resources
        console.log('Page hidden, polling continues...');
    }
});

// Add some utility functions for better UX
function showToast(message, type = 'info') {
    // Simple toast notification (could be enhanced with a proper toast library)
    const toast = document.createElement('div');
    toast.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: ${type === 'error' ? '#e53e3e' : '#667eea'};
        color: white;
        padding: 12px 20px;
        border-radius: 8px;
        z-index: 1000;
        box-shadow: 0 4px 16px rgba(0,0,0,0.2);
        animation: slideIn 0.3s ease;
    `;
    toast.textContent = message;
    
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => document.body.removeChild(toast), 300);
    }, 3000);
}

// Add CSS for toast animations
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    @keyframes slideOut {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(100%); opacity: 0; }
    }
`;
document.head.appendChild(style);