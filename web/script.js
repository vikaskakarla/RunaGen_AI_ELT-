// API Configuration
const API_BASE_URL = window.location.origin;

// DOM Elements
const uploadZone = document.getElementById('uploadZone');
const fileInput = document.getElementById('fileInput');
const fileInfo = document.getElementById('fileInfo');
const fileName = document.getElementById('fileName');
const fileSize = document.getElementById('fileSize');
const removeBtn = document.getElementById('removeBtn');
const analyzeBtn = document.getElementById('analyzeBtn');
const loadingCard = document.getElementById('loadingCard');
const errorCard = document.getElementById('errorCard');
const errorMessage = document.getElementById('errorMessage');
const resultsContainer = document.getElementById('resultsContainer');

let selectedFile = null;
let loadingStepIndex = 0;
let pdfDoc = null;
let pageNum = 1;
let pageRendering = false;
let pageNumPending = null;
let scale = 1.5;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    checkAPIHealth();
    setupEventListeners();
    
    // Initialize Guest ID
    const guestId = getGuestId();
    console.log('👤 Guest ID:', guestId);
    
    // Fetch history on load
    fetchHistory();
    
    // Set PDF.js worker
    if (typeof pdfjsLib !== 'undefined') {
        pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
    }
});

// Guest ID Management
function getGuestId() {
    let guestId = localStorage.getItem('runagen_guest_id');
    if (!guestId) {
        guestId = 'guest_' + Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);
        localStorage.setItem('runagen_guest_id', guestId);
    }
    return guestId;
}

// Setup Event Listeners
function setupEventListeners() {
    uploadZone.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', handleFileSelect);
    removeBtn.addEventListener('click', removeFile);
    analyzeBtn.addEventListener('click', analyzeResume);
    
    // Drag and drop
    uploadZone.addEventListener('dragover', handleDragOver);
    uploadZone.addEventListener('dragleave', handleDragLeave);
    uploadZone.addEventListener('drop', handleDrop);
    
    // Phase 3: Job Scraping
    document.getElementById('scrapeJobsBtn')?.addEventListener('click', scrapeJobs);
    
    // Phase 4: Learning Path
    document.getElementById('generatePathBtn')?.addEventListener('click', generateLearningPath);
    
    // Phase 5: Skill Trends
    document.getElementById('trendingSkillsBtn')?.addEventListener('click', getTrendingSkills);
    document.getElementById('emergingSkillsBtn')?.addEventListener('click', getEmergingSkills);
    
    // Phase 6: Resume Optimizer
    document.getElementById('optimizeResumeBtn')?.addEventListener('click', optimizeResume);
    
    // PDF Viewer Controls
    document.getElementById('prevPage')?.addEventListener('click', onPrevPage);
    document.getElementById('nextPage')?.addEventListener('click', onNextPage);
    document.getElementById('zoomIn')?.addEventListener('click', onZoomIn);
    document.getElementById('zoomOut')?.addEventListener('click', onZoomOut);
    
    // History Toggle
    document.getElementById('historyToggle')?.addEventListener('click', toggleHistory);
}

// File Selection
function handleFileSelect(e) {
    const file = e.target.files[0];
    if (file && file.type === 'application/pdf') {
        setFile(file);
    } else {
        showError('Please select a PDF file');
    }
}

function setFile(file) {
    selectedFile = file;
    fileName.textContent = file.name;
    fileSize.textContent = formatFileSize(file.size);
    fileInfo.style.display = 'flex';
    analyzeBtn.disabled = false;
    hideError();
}

function removeFile() {
    selectedFile = null;
    fileInput.value = '';
    fileInfo.style.display = 'none';
    analyzeBtn.disabled = true;
}

// Drag and Drop
function handleDragOver(e) {
    e.preventDefault();
    uploadZone.classList.add('dragover');
}

function handleDragLeave() {
    uploadZone.classList.remove('dragover');
}

function handleDrop(e) {
    e.preventDefault();
    uploadZone.classList.remove('dragover');
    
    const file = e.dataTransfer.files[0];
    if (file && file.type === 'application/pdf') {
        setFile(file);
    } else {
        showError('Please drop a PDF file');
    }
}

// Analyze Resume
async function analyzeResume() {
    if (!selectedFile) return;
    
    hideError();
    resultsContainer.style.display = 'none';
    loadingCard.style.display = 'block';
    
    // Animate loading steps
    animateLoadingSteps();
    
    try {
        const formData = new FormData();
        formData.append('file', selectedFile);
        formData.append('guest_id', getGuestId());
        
        const response = await fetch(`${API_BASE_URL}/api/upload-resume`, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: `HTTP ${response.status}` }));
            throw new Error(errorData.detail || `API Error: ${response.status}`);
        }
        
        const data = await response.json();
        console.log('✅ API Response:', data);
        console.log('📊 Skills:', data.skills);
        console.log('🚀 Career Predictions:', data.career_predictions);
        console.log('💰 Salary:', data.salary_prediction);
        console.log('📉 Skill Gaps:', data.skill_gaps);
        console.log('💼 Suggested Jobs:', data.suggested_jobs);
        
        displayResults(data);
        
        // Render charts after DOM is updated
        setTimeout(() => renderCharts(data), 100);
        
        loadingCard.style.display = 'none';
        resultsContainer.style.display = 'block';
        
        // Smooth scroll to results
        setTimeout(() => {
            resultsContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 100);
        
        // Refresh history
        fetchHistory();
        
    } catch (error) {
        loadingCard.style.display = 'none';
        showError(`⚠️ Analysis failed: ${error.message}. Make sure the API server is running.`);
    }
}

// Display Results
function displayResults(data) {
    console.log('🎨 Displaying results with data:', data);
    
    if (!data || typeof data !== 'object') {
        console.error('❌ Invalid data received:', data);
        showError('Invalid response from server');
        return;
    }
    
    resultsContainer.innerHTML = `
        ${createInfoCard(data)}
        ${createSkillsCard(data)}
        ${createCertificationsCard(data)}
        ${createCareerCard(data)}
        ${createSalaryCard(data)}
        ${createSkillGapCard(data)}
        ${createSuggestedJobsCard(data)}
        ${createRecommendationsCard(data)}
    `;
    
    // Load PDF viewer if file is selected or base64 PDF is present
    if (selectedFile || data.resume_pdf_base64) {
        // Add PDF viewer card to results
        const pdfViewerHTML = `
            <div class="result-card" id="pdfViewerCard">
                <div class="card-title">
                    <span class="card-icon">📄</span>
                    <h2>Your Resume</h2>
                </div>
                <div class="pdf-viewer-container">
                    <div class="pdf-controls">
                        <button class="pdf-control-btn" id="prevPage">← Previous</button>
                        <span class="pdf-page-info">
                            Page <span id="pageNum">1</span> of <span id="pageCount">1</span>
                        </span>
                        <button class="pdf-control-btn" id="nextPage">Next →</button>
                        <button class="pdf-control-btn" id="zoomOut">-</button>
                        <span class="pdf-zoom-info"><span id="zoomLevel">150</span>%</span>
                        <button class="pdf-control-btn" id="zoomIn">+</button>
                    </div>
                    <div class="pdf-canvas-wrapper">
                        <canvas id="pdfCanvas"></canvas>
                    </div>
                </div>
            </div>
        `;
        
        // Insert PDF viewer at the beginning
        resultsContainer.insertAdjacentHTML('afterbegin', pdfViewerHTML);
        
        // Re-attach event listeners for PDF controls
        document.getElementById('prevPage')?.addEventListener('click', onPrevPage);
        document.getElementById('nextPage')?.addEventListener('click', onNextPage);
        document.getElementById('zoomIn')?.addEventListener('click', onZoomIn);
        document.getElementById('zoomOut')?.addEventListener('click', onZoomOut);
        
        // Load the PDF
        if (selectedFile) {
            loadPDF(selectedFile);
        } else if (data.resume_pdf_base64) {
            console.log('📄 Loading PDF from history data...');
            const binaryString = window.atob(data.resume_pdf_base64);
            const bytes = new Uint8Array(binaryString.length);
            for (let i = 0; i < binaryString.length; i++) {
                bytes[i] = binaryString.charCodeAt(i);
            }
            const blob = new Blob([bytes], { type: 'application/pdf' });
            loadPDF(blob);
        }
    }
}

// Create Info Card
function createInfoCard(data) {
    return `
        <div class="result-card">
            <div class="card-title">
                <span class="card-icon">👤</span>
                <h2>Professional Profile</h2>
            </div>
            <div class="info-grid">
                <div class="info-box">
                    <div class="info-icon">⏳</div>
                    <div class="info-label">Experience</div>
                    <div class="info-value">${data.experience_years || '0'}Y</div>
                </div>
                <div class="info-box">
                    <div class="info-icon">🎓</div>
                    <div class="info-label">Education</div>
                    <div class="info-value" style="font-size: 1.2em; padding-top: 10px;">${data.education || 'N/A'}</div>
                </div>
                <div class="info-box">
                    <div class="info-icon">💎</div>
                    <div class="info-label">Skill Count</div>
                    <div class="info-value">${data.skills.length}</div>
                </div>
            </div>
        </div>
    `;
}

// Create Skills Card
function createSkillsCard(data) {
    if (!data.skills || data.skills.length === 0) {
        return `
            <div class="result-card">
                <div class="card-title">
                    <span class="card-icon">🛠️</span>
                    <h2>Your Skills</h2>
                </div>
                <p class="card-subtitle">No skills detected in your resume.</p>
            </div>
        `;
    }
    
    const skillsHTML = data.skills.map(skill => 
        `<div class="skill-badge">${skill}</div>`
    ).join('');
    
    return `
        <div class="result-card">
            <div class="card-title">
                <span class="card-icon">🛠️</span>
                <h2>Your Skills</h2>
            </div>
            <div class="skills-container">
                ${skillsHTML}
            </div>
        </div>
    `;
}

// Create Certifications Card
function createCertificationsCard(data) {
    if (!data.certifications || data.certifications.length === 0) {
        return `
            <div class="result-card">
                <div class="card-title">
                    <span class="card-icon">📜</span>
                    <h2>Certifications</h2>
                </div>
                <p class="card-subtitle">No professional certifications detected in your resume.</p>
            </div>
        `;
    }
    
    // Social links section
    const socialLinksHTML = data.social_links ? `
        <div class="social-verification-panel">
            <div class="panel-header">🔗 Digital Identity Verification</div>
            <div class="social-links-row">
                ${data.social_links.linkedin ? `
                    <div class="social-item found">
                        <span class="platform-icon">💼</span>
                        <a href="${data.social_links.linkedin}" target="_blank" class="platform-link">LinkedIn Profile</a>
                        <span class="status-indicator">Verified</span>
                    </div>
                ` : `
                    <div class="social-item missing">
                        <span class="platform-icon">💼</span>
                        <span class="platform-link">LinkedIn</span>
                        <span class="status-indicator">Not Found</span>
                    </div>
                `}
                ${data.social_links.github ? `
                    <div class="social-item found">
                        <span class="platform-icon">💻</span>
                        <a href="${data.social_links.github}" target="_blank" class="platform-link">GitHub Profile</a>
                        <span class="status-indicator">Verified</span>
                    </div>
                ` : `
                    <div class="social-item missing">
                        <span class="platform-icon">💻</span>
                        <span class="platform-link">GitHub</span>
                        <span class="status-indicator">Not Found</span>
                    </div>
                `}
                ${data.social_links.portfolio ? `
                    <div class="social-item found">
                        <span class="platform-icon">🌐</span>
                        <a href="${data.social_links.portfolio}" target="_blank" class="platform-link">Portfolio</a>
                        <span class="status-indicator">Active</span>
                    </div>
                ` : ''}
            </div>
            ${data.linkedin_verified_count > 0 ? `
                <div class="verification-badge-container">
                    <div class="verification-pill">
                        <span class="pill-icon">✅</span>
                        <span>${data.linkedin_verified_count} Credentials Verified via LinkedIn</span>
                    </div>
                </div>
            ` : ''}
        </div>
    ` : '';
    
    const certsHTML = data.certifications.map(cert => {
        const statusClass = `status-${cert.status_color}`;
        const scorePct = Math.round(cert.score * 100);
        const linkedinVerified = cert.linkedin_verified;
        const verificationSource = cert.verification_source || 'Resume Only';
        
        return `
            <div class="cert-item ${linkedinVerified ? 'is-verified' : ''}">
                <div class="cert-main">
                    <div class="cert-info">
                        <div class="cert-name">
                            ${cert.name}
                            ${linkedinVerified ? '<span class="verified-tag">VERIFIED</span>' : ''}
                        </div>
                        <div class="cert-issuer">${cert.issuer} ${cert.year ? `(${cert.year})` : ''}</div>
                        <div class="cert-id-row">
                            <span class="cert-id">${cert.verification_id ? `ID: ${cert.verification_id}` : 'Direct Link Found'}</span>
                            <span class="cert-source">• ${verificationSource}</span>
                        </div>
                    </div>
                    <div class="cert-status-container">
                        <div class="cert-status ${statusClass}">${cert.status}</div>
                        <div class="cert-reliability">Reliability: ${scorePct}%</div>
                    </div>
                </div>
            </div>
        `;
    }).join('');
    
    return `
        <div class="result-card">
            <div class="card-title">
                <span class="card-icon">📜</span>
                <h2>Professional Credentials</h2>
            </div>
            <p class="card-subtitle">AI-validated professional certifications with real-time profile cross-verification</p>
            ${socialLinksHTML}
            <div class="certs-container">
                ${certsHTML}
            </div>
        </div>
    `;
}

// Create Career Card
function createCareerCard(data) {
    console.log('🚀 Creating career card with:', data.career_predictions);
    
    if (!data.career_predictions || data.career_predictions.length === 0) {
        return `
            <div class="result-card">
                <div class="card-title">
                    <span class="card-icon">🚀</span>
                    <h2>Career Predictions</h2>
                </div>
                <p class="card-subtitle">No career predictions available</p>
            </div>
        `;
    }
    
    const careersHTML = data.career_predictions.map((pred, index) => {
        const percentage = (pred.probability * 100).toFixed(1);
        
        return `
            <div class="career-item">
                <div class="career-header">
                    <div class="career-rank">#${index + 1}</div>
                    <div class="career-name">${pred.role}</div>
                    <div class="career-percentage">${percentage}%</div>
                </div>
                <div class="career-description">${getCareerDescription(pred.probability)}</div>
            </div>
        `;
    }).join('');
    
    return `
        <div class="result-card">
            <div class="card-title">
                <span class="card-icon">🚀</span>
                <h2>Career Predictions</h2>
            </div>
            <p class="card-subtitle">AI-powered career path recommendations based on your profile</p>
            <div class="careers-layout">
                <div class="careers-container">
                    ${careersHTML}
                </div>
                <div class="chart-container-radar">
                    <canvas id="careerRadarChart"></canvas>
                </div>
            </div>
        </div>
    `;
}

// Create Salary Card
function createSalaryCard(data) {
    console.log('💰 Creating salary card with:', data.salary_prediction);
    
    if (!data.salary_prediction || !data.salary_prediction.predicted_salary) {
        return `
            <div class="result-card">
                <div class="card-title">
                    <span class="card-icon">💰</span>
                    <h2>Market Valuation</h2>
                </div>
                <p class="card-subtitle">Salary prediction not available</p>
            </div>
        `;
    }
    
    const salary = data.salary_prediction;
    const salaryLakhs = (salary.predicted_salary / 100000).toFixed(1);
    const minLakhs = (salary.min_salary / 100000).toFixed(1);
    const maxLakhs = (salary.max_salary / 100000).toFixed(1);
    
    return `
        <div class="result-card">
            <div class="card-title">
                <span class="card-icon">💰</span>
                <h2>Market Valuation</h2>
            </div>
            <div class="salary-layout">
                <div class="info-box" style="flex: 1; margin-top: 20px;">
                    <div class="info-label">Predicted Annual Salary</div>
                    <div class="info-value" style="font-size: 3.5em; color: var(--primary);">₹${salaryLakhs}L</div>
                    <p style="color: var(--text-secondary); margin-top: 10px;">
                        Market Range: <strong>₹${minLakhs}L - ₹${maxLakhs}L</strong>
                    </p>
                    <div class="badge" style="display: inline-flex; margin-top: 20px; box-shadow: none; background: rgba(255,255,255,0.05);">
                        <span class="badge-icon">🇮🇳</span>
                        <span>India Market Rate</span>
                    </div>
                </div>
                <div class="chart-container-salary">
                    <canvas id="salaryRangeChart"></canvas>
                </div>
            </div>
        </div>
    `;
}

// Create Skill Gap Card
function createSkillGapCard(data) {
    console.log('📉 Creating skill gap card with:', data.skill_gaps);
    
    if (!data.skill_gaps || data.skill_gaps.length === 0) {
        return `
            <div class="result-card">
                <div class="card-title">
                    <span class="card-icon">📉</span>
                    <h2>Growth Opportunities</h2>
                </div>
                <p class="card-subtitle">No skill gaps identified - you have all required skills!</p>
            </div>
        `;
    }
    
    const gapsHTML = data.skill_gaps.map(gap => {
        const priority = gap.priority_score > 0.8 ? 'High' : 
                        gap.priority_score > 0.6 ? 'Medium' : 'Low';
        
        return `
            <div class="recommendation-item">
                <div class="rec-icon">⚡</div>
                <div style="flex: 1;">
                    <div style="font-weight: 700; color: var(--text-primary); font-size: 1.1em;">${gap.skill}</div>
                    <div style="color: var(--text-secondary); font-size: 0.9em;">Priority Priority: ${priority}</div>
                </div>
            </div>
        `;
    }).join('');
    
    return `
        <div class="result-card">
            <div class="card-title">
                <span class="card-icon">📉</span>
                <h2>Growth Opportunities</h2>
            </div>
            <p class="card-subtitle">Master these missing skills to maximize your market value</p>
            <div class="skill-gap-layout">
                <div class="gaps-container" style="flex: 1.2; margin-top: 20px;">
                    ${gapsHTML}
                </div>
                <div class="chart-container-gap">
                    <canvas id="skillGapChart"></canvas>
                </div>
            </div>
        </div>
    `;
}

// Create Suggested Jobs Card
function createSuggestedJobsCard(data) {
    console.log('💼 Suggested Jobs in response:', data.suggested_jobs);
    
    let jobsHTML = '';
    
    if (!data.suggested_jobs || data.suggested_jobs.length === 0) {
        jobsHTML = `
            <div class="recommendation-item" style="display: block; opacity: 0.6; text-align: center; border-left: none;">
                <div style="font-size: 1.1em; color: var(--text-secondary);">No immediate job matches found for your predicted role. Try uploading your resume again or check back later.</div>
            </div>
        `;
    } else {
        jobsHTML = data.suggested_jobs.map(job => {
            const hasRealSalary = job.salary_min && job.salary_min > 10000;
            const minLakhs = hasRealSalary ? (job.salary_min / 100000).toFixed(1) : (data.salary_prediction?.min_salary / 100000).toFixed(1);
            const maxLakhs = hasRealSalary ? (job.salary_max / 100000).toFixed(1) : (data.salary_prediction?.max_salary / 100000).toFixed(1);
            
            let salaryText = `₹${minLakhs}L`;
            if (minLakhs !== maxLakhs) {
                salaryText = `₹${minLakhs}L - ₹${maxLakhs}L`;
            }
            
            if (!hasRealSalary) {
                if (job.is_actual_bigquery) {
                    salaryText += ' <span style="font-size: 0.7em; background: #059669; color: white; padding: 2px 6px; border-radius: 4px; vertical-align: middle; margin-left: 5px;">BIGQUERY ACTUAL</span>';
                } else {
                    salaryText += ' (Est.)';
                }
            }
            
            return `
                <div class="recommendation-item job-item" style="display: block;">
                    <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 10px;">
                        <div style="font-weight: 700; color: var(--primary); font-size: 1.2em;">${job.title}</div>
                        <div class="career-percentage" style="font-size: 0.8em;">LIVE MATCH</div>
                    </div>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 10px;">
                        <div style="color: var(--text-secondary); font-size: 0.9em;">🏢 ${job.company}</div>
                        <div style="color: var(--text-secondary); font-size: 0.9em;">📍 ${job.location}</div>
                    </div>
                    <div style="color: var(--accent-green); font-weight: 600;">💰 ${salaryText}</div>
                </div>
            `;
        }).join('');
    }
    
    return `
        <div class="result-card" id="suggestedJobsCard">
            <div class="card-title">
                <span class="card-icon">💼</span>
                <h2>Real-Time Job Matches</h2>
            </div>
            <p class="card-subtitle">Live job openings from BigQuery matching your top predicted career path</p>
            <div class="jobs-container" style="margin-top: 20px;">
                ${jobsHTML}
            </div>
        </div>
    `;
}

// Create Recommendations Card
function createRecommendationsCard(data) {
    console.log('💡 Creating recommendations card with:', data.recommendations);
    
    if (!data.recommendations || data.recommendations.length === 0) {
        return `
            <div class="result-card">
                <div class="card-title">
                    <span class="card-icon">💡</span>
                    <h2>Strategic Career Advice</h2>
                </div>
                <p class="card-subtitle">No recommendations available</p>
            </div>
        `;
    }
    
    const recsHTML = data.recommendations.map(rec => 
        `<div class="recommendation-item">
            <div class="rec-icon">✨</div>
            <div class="rec-text">${rec}</div>
        </div>`
    ).join('');
    
    return `
        <div class="result-card">
            <div class="card-title">
                <span class="card-icon">💡</span>
                <h2>Strategic Career Advice</h2>
            </div>
            <div class="recommendations-list">
                ${recsHTML}
            </div>
        </div>
    `;
}

// Render Charts Function
function renderCharts(data) {
    // 0. Global Check for Chart.js
    if (typeof Chart === 'undefined') {
        console.error('❌ Chart.js is not defined. Graphics will not be rendered.');
        showError('Data visualizations could not be loaded. Please check your internet connection.');
        return;
    }

    // 1. Career Radar Chart
    try {
        if (data.career_predictions && data.career_predictions.length > 0) {
            const canvas = document.getElementById('careerRadarChart');
            if (canvas) {
                const ctx = canvas.getContext('2d');
                const roles = data.career_predictions.slice(0, 5).map(p => p.role);
                const probs = data.career_predictions.slice(0, 5).map(p => p.probability * 100);
                
                new Chart(ctx, {
                    type: 'radar',
                    data: {
                        labels: roles,
                        datasets: [{
                            label: 'Match Probability (%)',
                            data: probs,
                            backgroundColor: 'rgba(245, 158, 11, 0.2)',
                            borderColor: '#f59e0b',
                            pointBackgroundColor: '#f59e0b',
                            pointBorderColor: '#fff',
                            pointHoverBackgroundColor: '#fff',
                            pointHoverBorderColor: '#f59e0b'
                        }]
                    },
                    options: {
                        scales: {
                            r: {
                                angleLines: { color: 'rgba(255, 255, 255, 0.1)' },
                                grid: { color: 'rgba(255, 255, 255, 0.1)' },
                                pointLabels: { color: '#94a3b8', font: { size: 12, family: 'Outfit' } },
                                ticks: { display: false, stepSize: 20 },
                                suggestedMin: 0,
                                suggestedMax: 100
                            }
                        },
                        plugins: {
                            legend: { display: false }
                        }
                    }
                });
            }
        }
    } catch (e) {
        console.error('Error rendering Career Radar Chart:', e);
    }

    // 2. Skill Gap Analysis Chart (Priority Distribution)
    try {
        if (data.skill_gaps && data.skill_gaps.length > 0) {
            const canvas = document.getElementById('skillGapChart');
            if (canvas) {
                const ctx = canvas.getContext('2d');
                const labels = data.skill_gaps.slice(0, 7).map(g => g.skill);
                const scores = data.skill_gaps.slice(0, 7).map(g => (g.priority_score || 0) * 100);

                new Chart(ctx, {
                    type: 'bar',
                    data: {
                        labels: labels,
                        datasets: [{
                            label: 'Priority Score',
                            data: scores,
                            backgroundColor: 'rgba(56, 189, 248, 0.6)',
                            borderColor: '#38bdf8',
                            borderWidth: 1,
                            borderRadius: 8
                        }]
                    },
                    options: {
                        indexAxis: 'y',
                        scales: {
                            x: {
                                grid: { display: false },
                                ticks: { color: '#64748b' },
                                suggestedMax: 100
                            },
                            y: {
                                grid: { color: 'rgba(255, 255, 255, 0.05)' },
                                ticks: { color: '#cbd5e1' }
                            }
                        },
                        plugins: {
                            legend: { display: false }
                        }
                    }
                });
            }
        }
    } catch (e) {
        console.error('Error rendering Skill Gap Chart:', e);
    }

    // 3. Salary Range Chart
    try {
        if (data.salary_prediction) {
            const canvas = document.getElementById('salaryRangeChart');
            if (canvas) {
                const ctx = canvas.getContext('2d');
                const sal = data.salary_prediction;
                
                new Chart(ctx, {
                    type: 'doughnut',
                    data: {
                        labels: ['Min Market', 'Your Prediction', 'Max Market'],
                        datasets: [{
                            data: [sal.min_salary, sal.predicted_salary, sal.max_salary],
                            backgroundColor: [
                                'rgba(245, 158, 11, 0.1)',
                                '#f59e0b',
                                'rgba(245, 158, 11, 0.1)'
                            ],
                            borderWidth: 0,
                            circumference: 180,
                            rotation: 270,
                            cutout: '80%'
                        }]
                    },
                    options: {
                        plugins: {
                            legend: { display: false },
                            tooltip: { enabled: false }
                        }
                    }
                });
            }
        }
    } catch (e) {
        console.error('Error rendering Salary Range Chart:', e);
    }
}

// Helper Functions
function getCareerDescription(probability) {
    if (probability > 0.7) return 'Excellent match - Highly recommended career path';
    if (probability > 0.5) return 'Good match - Consider developing relevant skills';
    return 'Potential path - Requires significant skill development';
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

function animateLoadingSteps() {
    const steps = document.querySelectorAll('.step');
    loadingStepIndex = 0;
    
    const interval = setInterval(() => {
        if (loadingStepIndex < steps.length) {
            steps[loadingStepIndex].classList.add('active');
            loadingStepIndex++;
        } else {
            clearInterval(interval);
        }
    }, 1000);
}

function showError(message) {
    errorMessage.textContent = message;
    errorCard.style.display = 'flex';
    setTimeout(() => hideError(), 5000);
}

function hideError() {
    errorCard.style.display = 'none';
}

// Check API Health
async function checkAPIHealth() {
    try {
        const response = await fetch(`${API_BASE_URL}/health`);
        if (response.ok) {
            console.log('✓ API server is running');
        }
    } catch (error) {
        console.warn('⚠ API server is not running');
        showError('API server is not running. Please start it with: python3 src/api/main.py');
    }
}

// ===== PHASE 3: JOB SCRAPING =====
async function scrapeJobs() {
    const keywords = document.getElementById('jobKeywords').value;
    if (!keywords) {
        showError('Please enter job keywords');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/jobs/scrape?keywords=${keywords}&location=India`);
        const data = await response.json();
        
        if (data.jobs && data.jobs.length > 0) {
            const jobsHTML = data.jobs.map(job => {
                const minLakhs = (job.salary_min / 100000).toFixed(1);
                const maxLakhs = (job.salary_max / 100000).toFixed(1);
                let salaryText = 'Competitive';
                
                if (job.salary_min > 0 && job.salary_max > 0) {
                    if (minLakhs === maxLakhs) {
                        salaryText = `₹${minLakhs}L`;
                    } else {
                        salaryText = `₹${minLakhs}L - ₹${maxLakhs}L`;
                    }
                }
                
                return `
                    <div class="job-card">
                        <h3>${job.title}</h3>
                        <p><strong>${job.company}</strong> - ${job.location}</p>
                        <p style="color: var(--accent-green); font-weight: 600;">💰 ${salaryText}</p>
                        <a href="${job.url}" target="_blank" class="feature-btn">View Job</a>
                    </div>
                `;
            }).join('');
            document.getElementById('jobResults').innerHTML = jobsHTML;
        }
    } catch (error) {
        showError(`Job scraping failed: ${error.message}`);
    }
}

// ===== PHASE 4: LEARNING PATH =====
async function generateLearningPath() {
    const career = document.getElementById('targetCareer').value;
    if (!career) {
        showError('Please enter a target career');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/learning-path`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                career: career,
                current_skills: [],
                target_level: 'intermediate'
            })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.learning_path && data.learning_path.phases) {
            const path = data.learning_path;
            
            // Display overview
            const overviewHTML = `
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 25px; border-radius: 12px; margin-bottom: 20px; color: white;">
                    <h3 style="margin: 0 0 15px 0;">Learning Path for ${path.career}</h3>
                    <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 15px; font-size: 0.95em;">
                        <div>📚 ${path.phases.length} Phases</div>
                        <div>⏱️ ${path.total_hours_required} Hours</div>
                        <div>📅 ~${Math.ceil(path.estimated_weeks)} Weeks</div>
                    </div>
                </div>
            `;
            
            // Display phases
            const phasesHTML = path.phases.map((phase, index) => `
                <div style="background: #1e293b; padding: 25px; border-radius: 12px; margin-bottom: 20px; border-left: 4px solid ${
                    index === 0 ? '#ef4444' : index === 1 ? '#f59e0b' : '#3b82f6'
                };">
                    <h4 style="margin: 0 0 15px 0; color: #f1f5f9; font-size: 1.3em;">${phase.name}</h4>
                    <div style="display: flex; gap: 20px; margin-bottom: 15px; color: #94a3b8; font-size: 0.9em;">
                        <span>⏱️ ${phase.total_hours} hours</span>
                        <span>💰 ₹${phase.total_cost}</span>
                        <span>📊 Priority ${phase.priority}</span>
                    </div>
                    <div style="margin-top: 20px;">
                        ${phase.skills.map(skillEntry => `
                            <div style="background: rgba(255,255,255,0.05); padding: 15px; border-radius: 8px; margin-bottom: 12px;">
                                <div style="font-weight: 600; color: #f1f5f9; margin-bottom: 8px;">📖 ${skillEntry.skill}</div>
                                ${skillEntry.resources.map(resource => `
                                    <div style="color: #cbd5e1; font-size: 0.9em; margin-left: 20px;">
                                        <div>📚 ${resource.name} (${resource.platform})</div>
                                        <div style="color: #94a3b8; margin-top: 4px;">
                                            ⏱️ ${resource.duration_hours}h • 
                                            ${resource.cost > 0 ? `💰 ₹${resource.cost}` : '🆓 Free'} • 
                                            📊 ${resource.difficulty}
                                        </div>
                                    </div>
                                `).join('')}
                            </div>
                        `).join('')}
                    </div>
                </div>
            `).join('');
            
            // Display recommendations
            const recsHTML = path.recommendations && path.recommendations.length > 0 ? `
                <div style="background: #fef3c7; padding: 20px; border-radius: 8px; border-left: 4px solid #f59e0b;">
                    <h4 style="margin: 0 0 15px 0; color: #92400e;">💡 Recommendations</h4>
                    <ul style="margin: 0; padding-left: 20px; color: #78350f;">
                        ${path.recommendations.map(rec => `<li style="margin: 8px 0;">${rec}</li>`).join('')}
                    </ul>
                </div>
            ` : '';
            
            document.getElementById('learningResults').innerHTML = overviewHTML + phasesHTML + recsHTML;
        } else {
            showError('No learning path data available');
        }
    } catch (error) {
        showError(`Learning path generation failed: ${error.message}`);
    }
}

// ===== PHASE 5: SKILL TRENDS =====
let trendChart = null;

async function getTrendingSkills() {
    console.log('📊 Fetching trending skills...');
    const role = document.getElementById('targetRole').value;
    const url = role ? 
        `${API_BASE_URL}/api/skill-trends/trending?days=30&limit=10&role=${encodeURIComponent(role)}` : 
        `${API_BASE_URL}/api/skill-trends/trending?days=30&limit=10`;
        
    try {
        const response = await fetch(url);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        
        console.log('✅ Trending data received:', data);
        
        if (data.trending_skills) {
            // Render Skill Cards
            const skillsHTML = data.trending_skills.map(skill => `
                <div class="trend-card" style="border-left: 4px solid var(--primary); padding: 15px; background: rgba(255,255,255,0.02); border-radius: 8px;">
                    <h4 style="color: var(--primary); margin: 0 0 8px 0; font-size: 1.1em;">${skill.skill_name}</h4>
                    <div style="font-size: 0.85em; color: var(--text-secondary); margin-bottom: 5px;">🔥 Trending in ${data.role || 'Market'}</div>
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 10px;">
                        <span style="font-weight: 600; color: var(--accent-green); font-size: 0.9em;">${skill.demand_percentage}% Share</span>
                        <span style="font-size: 0.8em; opacity: 0.7;">${skill.demand_count} jobs</span>
                    </div>
                </div>
            `).join('');
            document.getElementById('trendResults').innerHTML = skillsHTML;
            
            // Render Chart
            if (data.graph_data) {
                console.log('📈 Rendering trending chart...');
                renderTrendChart(data.graph_data);
            }
        }
    } catch (error) {
        console.error('❌ Trending skills error:', error);
        showError(`Trending skills failed: ${error.message}`);
    }
}

async function getEmergingSkills() {
    console.log('🚀 Fetching emerging skills...');
    const role = document.getElementById('targetRole').value;
    const url = role ? 
        `${API_BASE_URL}/api/skill-trends/emerging?threshold_days=30&role=${encodeURIComponent(role)}` : 
        `${API_BASE_URL}/api/skill-trends/emerging?threshold_days=30`;
        
    try {
        const response = await fetch(url);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        
        console.log('✅ Emerging data received:', data);
        
        if (data.emerging_skills) {
            if (data.emerging_skills.length === 0) {
                document.getElementById('trendResults').innerHTML = '<p style="grid-column: 1/-1; text-align: center; padding: 20px;">No specific emerging skills detected for this role yet.</p>';
                document.getElementById('trendChartContainer').style.display = 'none';
                return;
            }

            const skillsHTML = data.emerging_skills.map(skill => `
                <div class="trend-card" style="border-left: 4px solid var(--accent-green); padding: 15px; background: rgba(255,255,255,0.02); border-radius: 8px;">
                    <h4 style="color: var(--accent-green); margin: 0 0 8px 0; font-size: 1.1em;">${skill.skill_name}</h4>
                    <div style="font-size: 0.85em; color: var(--text-secondary); margin-bottom: 5px;">🚀 Emerging for ${data.role || 'Market'}</div>
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 10px;">
                        <span style="font-weight: 600; color: var(--primary); font-size: 0.9em;">Score: ${skill.emergence_score}</span>
                        <span style="font-size: 0.75em; opacity: 0.7;">First seen: ${new Date(skill.first_seen).toLocaleDateString()}</span>
                    </div>
                </div>
            `).join('');
            document.getElementById('trendResults').innerHTML = skillsHTML;
            
            // For emerging, we'll create a simple growth chart
            const graphData = {
                type: 'bar',
                title: `Emerging Skills Growth (${data.role || 'Market'})`,
                labels: data.emerging_skills.map(s => s.skill_name),
                datasets: [{
                    label: 'Emergence Score',
                    data: data.emerging_skills.map(s => s.emergence_score),
                    backgroundColor: 'rgba(16, 185, 129, 0.6)',
                    borderColor: 'rgba(16, 185, 129, 1)',
                    borderWidth: 1
                }]
            };
            renderTrendChart(graphData);
        }
    } catch (error) {
        console.error('❌ Emerging skills error:', error);
        showError(`Emerging skills failed: ${error.message}`);
    }
}

function renderTrendChart(graphData) {
    console.log('📈 Attempting to render chart with data:', graphData);
    const container = document.getElementById('trendChartContainer');
    const canvas = document.getElementById('trendChart');
    
    if (!canvas) {
        console.error('❌ trendChart canvas not found in DOM!');
        return;
    }
    
    if (!graphData || !graphData.labels || graphData.labels.length === 0) {
        console.warn('⚠️ No graph data available to render');
        container.style.display = 'none';
        return;
    }

    const ctx = canvas.getContext('2d');
    container.style.display = 'block';
    
    // Clear previous chart instance
    if (trendChart) {
        trendChart.destroy();
    }
    
    try {
        trendChart = new Chart(ctx, {
            type: graphData.type || 'bar',
            data: {
                labels: graphData.labels,
                datasets: graphData.datasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: {
                    duration: 1000,
                    easing: 'easeOutQuart'
                },
                plugins: {
                    title: {
                        display: true,
                        text: graphData.title,
                        color: '#f1f5f9',
                        font: { size: 18, family: 'Outfit', weight: '700' }
                    },
                    legend: {
                        position: 'top',
                        labels: { color: '#94a3b8', font: { family: 'Outfit' }, padding: 20 }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(15, 23, 42, 0.9)',
                        titleFont: { family: 'Outfit' },
                        bodyFont: { family: 'Outfit' }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        ticks: { color: '#94a3b8', font: { family: 'Outfit' } }
                    },
                    x: {
                        grid: { display: false },
                        ticks: { color: '#94a3b8', font: { family: 'Outfit' } }
                    }
                }
            }
        });
        console.log('✅ Chart rendered successfully');
    } catch (chartError) {
        console.error('❌ Chart.js rendering error:', chartError);
    }
}

// ===== PHASE 6: RESUME OPTIMIZER =====
async function optimizeResume() {
    const targetRole = document.getElementById('targetRole').value;
    if (!targetRole) {
        showError('Please enter a target role');
        return;
    }
    
    if (!selectedFile) {
        showError('Please upload and analyze a resume first');
        return;
    }
    
    try {
        // Use empty resume_text - backend will use cached version
        const response = await fetch(`${API_BASE_URL}/api/resume/optimize`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                resume_text: 'USE_CACHED',  // Signal to use cached resume
                target_role: targetRole
            })
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `HTTP ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.optimization && data.optimization.optimization_suggestions) {
            const opt = data.optimization;
            
            // Display ATS Score
            const atsScoreHTML = opt.ats_score ? `
                <div class="ats-score-card" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 12px; margin-bottom: 20px; color: white;">
                    <h3 style="margin: 0 0 10px 0;">ATS Compatibility Score</h3>
                    <div style="font-size: 3em; font-weight: bold; margin: 10px 0;">${opt.ats_score.overall_score}/100</div>
                    <div style="font-size: 1.2em; opacity: 0.9;">${opt.ats_score.rating} - ${opt.ats_score.pass_probability} pass probability</div>
                    <div style="margin-top: 20px; display: grid; grid-template-columns: 1fr 1fr; gap: 15px; font-size: 0.9em;">
                        <div>📊 Keyword Match: ${opt.ats_score.keyword_match.toFixed(1)}%</div>
                        <div>📝 Formatting: ${opt.ats_score.formatting_score}/100</div>
                    </div>
                </div>
            ` : '';
            
            // Display Quick Wins
            const quickWinsHTML = opt.quick_wins && opt.quick_wins.length > 0 ? `
                <div style="background: #fef3c7; padding: 20px; border-radius: 8px; margin-bottom: 20px; border-left: 4px solid #f59e0b;">
                    <h4 style="margin: 0 0 15px 0; color: #92400e;">⚡ Quick Wins (Fix These First)</h4>
                    ${opt.quick_wins.map(win => `
                        <div style="margin-bottom: 10px; padding: 10px; background: white; border-radius: 6px;">
                            <strong>[${win.priority}] ${win.action}</strong>
                            <p style="margin: 5px 0; color: #666;">${win.details}</p>
                        </div>
                    `).join('')}
                </div>
            ` : '';
            
            // Display all suggestions with how-to-fix
            const suggestionsHTML = opt.optimization_suggestions.map(sug => `
                <div class="suggestion-card" style="margin-bottom: 20px; padding: 20px; background: #1e293b; border-radius: 8px; border-left: 4px solid ${
                    sug.priority === 'CRITICAL' ? '#ef4444' : 
                    sug.priority === 'HIGH' ? '#f59e0b' : 
                    sug.priority === 'MEDIUM' ? '#3b82f6' : '#6b7280'
                };">
                    <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 10px;">
                        <h4 style="margin: 0; color: #f1f5f9;">[${sug.priority}] ${sug.action}</h4>
                        <span style="background: rgba(255,255,255,0.1); padding: 4px 12px; border-radius: 12px; font-size: 0.85em;">${sug.category}</span>
                    </div>
                    <p style="color: #cbd5e1; margin: 10px 0;">${sug.details}</p>
                    <p style="color: #10b981; font-weight: 600; margin: 10px 0;">💡 ${sug.impact}</p>
                    ${sug.how_to_fix ? `
                        <div style="margin-top: 15px; padding: 15px; background: rgba(255,255,255,0.05); border-radius: 6px;">
                            <strong style="color: #f1f5f9;">How to Fix:</strong>
                            <ul style="margin: 10px 0; padding-left: 20px; color: #cbd5e1;">
                                ${sug.how_to_fix.map(fix => `<li style="margin: 5px 0;">${fix}</li>`).join('')}
                            </ul>
                        </div>
                    ` : ''}
                </div>
            `).join('');
            
            document.getElementById('optimizeResults').innerHTML = atsScoreHTML + quickWinsHTML + suggestionsHTML;
        } else {
            showError('No optimization suggestions available');
        }
    } catch (error) {
        showError(`Resume optimization failed: ${error.message}`);
    }
}


// ===== PDF VIEWER FUNCTIONS =====

/**
 * Load and display PDF from file
 */
async function loadPDF(file) {
    if (typeof pdfjsLib === 'undefined') {
        console.error('PDF.js library not loaded');
        showError('PDF viewer not available. Please refresh the page.');
        return;
    }
    
    try {
        const arrayBuffer = await file.arrayBuffer();
        const loadingTask = pdfjsLib.getDocument({ data: arrayBuffer });
        
        pdfDoc = await loadingTask.promise;
        document.getElementById('pageCount').textContent = pdfDoc.numPages;
        
        // Show PDF viewer card
        const pdfViewerCard = document.getElementById('pdfViewerCard');
        if (pdfViewerCard) {
            pdfViewerCard.style.display = 'block';
        }
        
        // Render first page
        renderPage(pageNum);
        
        console.log('✅ PDF loaded successfully:', pdfDoc.numPages, 'pages');
    } catch (error) {
        console.error('❌ Error loading PDF:', error);
        showError('Failed to load PDF viewer');
    }
}

/**
 * Render a specific page
 */
function renderPage(num) {
    if (!pdfDoc) return;
    
    pageRendering = true;
    
    pdfDoc.getPage(num).then(page => {
        const canvas = document.getElementById('pdfCanvas');
        const ctx = canvas.getContext('2d');
        const viewport = page.getViewport({ scale: scale });
        
        canvas.height = viewport.height;
        canvas.width = viewport.width;
        
        const renderContext = {
            canvasContext: ctx,
            viewport: viewport
        };
        
        const renderTask = page.render(renderContext);
        
        renderTask.promise.then(() => {
            pageRendering = false;
            if (pageNumPending !== null) {
                renderPage(pageNumPending);
                pageNumPending = null;
            }
        });
    });
    
    document.getElementById('pageNum').textContent = num;
    
    // Update button states
    document.getElementById('prevPage').disabled = (num <= 1);
    document.getElementById('nextPage').disabled = (num >= pdfDoc.numPages);
}

/**
 * Queue page rendering
 */
function queueRenderPage(num) {
    if (pageRendering) {
        pageNumPending = num;
    } else {
        renderPage(num);
    }
}

/**
 * Previous page
 */
function onPrevPage() {
    if (pageNum <= 1) return;
    pageNum--;
    queueRenderPage(pageNum);
}

/**
 * Next page
 */
function onNextPage() {
    if (pageNum >= pdfDoc.numPages) return;
    pageNum++;
    queueRenderPage(pageNum);
}

/**
 * Zoom in
 */
function onZoomIn() {
    scale += 0.25;
    if (scale > 3) scale = 3;
    document.getElementById('zoomLevel').textContent = Math.round(scale * 100);
    queueRenderPage(pageNum);
}

/**
 * Zoom out
 */
function onZoomOut() {
    scale -= 0.25;
    if (scale < 0.5) scale = 0.5;
    document.getElementById('zoomLevel').textContent = Math.round(scale * 100);
    queueRenderPage(pageNum);
}

// History Management
async function fetchHistory() {
    const guestId = getGuestId();
    try {
        const response = await fetch(`${API_BASE_URL}/api/history/${guestId}`);
        if (response.ok) {
            const data = await response.json();
            displayHistory(data.history);
        }
    } catch (error) {
        console.error('Error fetching history:', error);
    }
}

function displayHistory(history) {
    const historyContainer = document.getElementById('historyList');
    if (!historyContainer) return;
    
    if (!history || history.length === 0) {
        historyContainer.innerHTML = '<div class="history-empty">No history found. Upload a resume to start!</div>';
        return;
    }
    
    historyContainer.innerHTML = history.map(item => `
        <div class="history-item" onclick="loadHistoryRecord('${item.id}')">
            <div class="history-item-icon">📄</div>
            <div class="history-item-info">
                <div class="history-item-title">${item.filename || 'Resume'}</div>
                <div class="history-item-role">${item.analysis_results?.career_predictions?.[0]?.role || item.career || 'Analysis'}</div>
                <div class="history-item-date">${new Date(item.timestamp).toLocaleDateString()}</div>
            </div>
        </div>
    `).join('');
}

function toggleHistory() {
    const historyPanel = document.getElementById('historyPanel');
    if (historyPanel) {
        historyPanel.classList.toggle('open');
    }
}

async function loadHistoryRecord(recordId) {
    hideError();
    resultsContainer.style.display = 'none';
    loadingCard.style.display = 'block';
    
    // Toggle history panel closed
    const historyPanel = document.getElementById('historyPanel');
    if (historyPanel) historyPanel.classList.remove('open');
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/history/record/${recordId}`);
        if (!response.ok) throw new Error('Failed to load history record');
        
        const data = await response.json();
        const record = data.record;
        
        // Map history record to expected analysis format
        const analysisData = {
            ...record.analysis_results,
            ...record.extracted_data,
            resume_pdf_base64: record.resume_pdf_base64,
            analysis_timestamp: record.timestamp,
            education: record.extracted_data.education
        };
        
        displayResults(analysisData);
        setTimeout(() => renderCharts(analysisData), 100);
        
        loadingCard.style.display = 'none';
        resultsContainer.style.display = 'block';
        resultsContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
        
    } catch (error) {
        loadingCard.style.display = 'none';
        showError(`⚠️ Failed to load history: ${error.message}`);
    }
}
