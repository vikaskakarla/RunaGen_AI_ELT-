/**
 * RunaGen AI — Live Pipeline Dashboard
 * Auto-polls the server and displays real-time pipeline + market data.
 */

const API = window.location.origin;
let pollTimer = null;
let dashboardRefreshTimer = null;

// ═══════════════════════════════════════════
// Initialization
// ═══════════════════════════════════════════
document.addEventListener('DOMContentLoaded', () => {
    // Initial load
    fetchPipelineStatus();
    fetchDashboardData();

    // Poll pipeline status every 3 seconds while it's running, else every 30s
    startPipelinePolling();

    // Refresh dashboard data every 60 seconds
    dashboardRefreshTimer = setInterval(fetchDashboardData, 60000);

    // Manual refresh button
    document.getElementById('refreshBtn')?.addEventListener('click', () => {
        fetchPipelineStatus();
        fetchDashboardData();
    });
});

// ═══════════════════════════════════════════
// Pipeline Status Polling
// ═══════════════════════════════════════════
let lastPipelineState = 'idle';

function startPipelinePolling() {
    fetchPipelineStatus();
    // Adaptive polling: fast while running, slow when done
    pollTimer = setInterval(() => {
        fetchPipelineStatus();
    }, lastPipelineState === 'running' || lastPipelineState === 'checking' ? 3000 : 30000);
}

async function fetchPipelineStatus() {
    try {
        const res = await fetch(`${API}/api/live/pipeline-run-status`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        renderPipelineStatus(data);

        // Adjust polling speed
        if (data.state !== lastPipelineState) {
            lastPipelineState = data.state;
            clearInterval(pollTimer);
            const interval = (data.state === 'running' || data.state === 'checking') ? 3000 : 30000;
            pollTimer = setInterval(fetchPipelineStatus, interval);
        }
    } catch (e) {
        console.warn('Pipeline status fetch failed:', e);
    }
}

function renderPipelineStatus(data) {
    const banner = document.getElementById('pipelineBanner');
    const dot = document.getElementById('statusDot');
    const stateLabel = document.getElementById('pipelineStateLabel');
    const messageEl = document.getElementById('pipelineMessage');
    const progressFill = document.getElementById('progressFill');
    const spinner = document.getElementById('refreshSpinner');

    // State label
    const stateText = {
        idle: 'Idle',
        checking: 'Checking...',
        running: 'Running',
        completed: 'Completed',
        failed: 'Failed'
    };
    stateLabel.textContent = stateText[data.state] || data.state;

    // Status dot
    dot.className = `status-dot ${data.state}`;

    // Banner class
    banner.className = `pipeline-banner ${data.state === 'running' ? 'running' : ''}`;

    // Message
    messageEl.textContent = data.message || '';

    // Progress bar
    progressFill.style.width = `${data.progress_pct || 0}%`;

    // Spinner
    spinner.className = `refresh-spinner ${(data.state === 'running' || data.state === 'checking') ? 'active' : ''}`;

    // Stage indicators
    const stages = ['data_fetch', 'etl', 'model_training'];
    stages.forEach(stage => {
        const el = document.getElementById(`stage-${stage}`);
        if (!el) return;

        el.className = 'stage-item';
        if (data.current_stage === stage && data.state === 'running') {
            el.classList.add('active');
        } else if (data.last_run_result?.stages?.[stage]?.success) {
            el.classList.add('done');
        } else if (data.last_run_result?.stages?.[stage]?.success === false) {
            el.classList.add('failed');
        }
    });
}

// ═══════════════════════════════════════════
// Dashboard Data (Stats, Skills, Jobs, Health)
// ═══════════════════════════════════════════
async function fetchDashboardData() {
    try {
        // Fetch all data in parallel
        const [statusRes, trendsRes, healthRes, jobsRes, skillsRes] = await Promise.allSettled([
            fetch(`${API}/api/live/status`),
            fetch(`${API}/api/live/market-trends`),
            fetch(`${API}/api/live/pipeline-health`),
            fetch(`${API}/api/live/jobs/recent?limit=8&hours=72`),
            fetch(`${API}/api/live/skills/trending?limit=10`)
        ]);

        // Parse responses
        const status = statusRes.status === 'fulfilled' && statusRes.value.ok
            ? await statusRes.value.json() : null;
        const trends = trendsRes.status === 'fulfilled' && trendsRes.value.ok
            ? await trendsRes.value.json() : null;
        const health = healthRes.status === 'fulfilled' && healthRes.value.ok
            ? await healthRes.value.json() : null;
        const jobs = jobsRes.status === 'fulfilled' && jobsRes.value.ok
            ? await jobsRes.value.json() : null;
        const skills = skillsRes.status === 'fulfilled' && skillsRes.value.ok
            ? await skillsRes.value.json() : null;

        // Render everything
        renderStats(status);
        renderTrendingSkills(skills);
        renderRecentJobs(jobs);
        renderHealth(health);
        renderMarketInsights(trends);

        // Update last-refreshed timestamp
        document.getElementById('lastRefresh').textContent =
            `Last refreshed: ${new Date().toLocaleTimeString()}`;

    } catch (e) {
        console.error('Dashboard data fetch failed:', e);
    }
}

// ═══ Stats ═══
function renderStats(data) {
    if (!data) return;

    setTextContent('statTotalJobs', formatNumber(data.total_jobs || 0));
    setTextContent('statActiveJobs', formatNumber(data.active_jobs || 0));
    setTextContent('statRecent24h', formatNumber(data.recent_jobs_24h || 0));
    setTextContent('statTotalSkills', formatNumber(data.total_skills || 0));
    setTextContent('statTrendingSkills', formatNumber(data.trending_skills || 0));

    const freshness = data.data_freshness_hours;
    const freshnessEl = document.getElementById('statFreshness');
    if (freshnessEl) {
        if (freshness === null || freshness === undefined) {
            freshnessEl.textContent = '—';
            freshnessEl.className = 'stat-value';
        } else if (freshness < 2) {
            freshnessEl.textContent = `${freshness.toFixed(1)}h`;
            freshnessEl.className = 'stat-value green';
        } else if (freshness < 6) {
            freshnessEl.textContent = `${freshness.toFixed(1)}h`;
            freshnessEl.className = 'stat-value amber';
        } else {
            freshnessEl.textContent = `${freshness.toFixed(1)}h`;
            freshnessEl.className = 'stat-value red';
        }
    }
}

// ═══ Trending Skills ═══
function renderTrendingSkills(data) {
    const container = document.getElementById('trendingSkillsList');
    if (!container || !data?.trending_skills) {
        if (container) container.innerHTML = '<div class="loading-placeholder">No skills data yet</div>';
        return;
    }

    const maxCount = Math.max(...data.trending_skills.map(s => s.demand_count || 1), 1);

    container.innerHTML = data.trending_skills.map(skill => `
        <div class="skill-row">
            <span class="skill-name">${skill.skill_name}</span>
            <div class="skill-bar-container">
                <div class="skill-bar" style="width: ${(skill.demand_count / maxCount * 100).toFixed(0)}%"></div>
            </div>
            <span class="skill-count">${skill.demand_count}</span>
            ${skill.total_mentions > skill.demand_count * 2 ? '<span class="trending-badge">🔥 Hot</span>' : ''}
        </div>
    `).join('');
}

// ═══ Recent Jobs ═══
function renderRecentJobs(data) {
    const container = document.getElementById('recentJobsList');
    if (!container || !data?.jobs?.length) {
        if (container) container.innerHTML = '<div class="loading-placeholder">No recent jobs yet</div>';
        return;
    }

    container.innerHTML = data.jobs.map(job => `
        <div class="job-item">
            <div class="job-title">${escapeHtml(job.title)}</div>
            <div class="job-meta">
                <span>🏢 ${escapeHtml(job.company || 'Company')}</span>
                <span>📍 ${escapeHtml(job.location || 'India')}</span>
                ${job.salary_min ? `<span>💰 ₹${(job.salary_min/100000).toFixed(1)}L - ₹${(job.salary_max/100000).toFixed(1)}L</span>` : ''}
                <span>📡 ${job.source || 'live'}</span>
            </div>
        </div>
    `).join('');
}

// ═══ Health ═══
function renderHealth(data) {
    const container = document.getElementById('healthGrid');
    if (!container || !data) return;

    const components = data.components || {};
    const items = [
        { label: 'Data Ingestion', status: components.data_ingestion || 'unknown' },
        { label: 'ETL Pipeline', status: components.etl_pipeline || 'unknown' },
        { label: 'ML Training', status: components.model_training || 'unknown' },
        { label: 'MongoDB', status: components.mongodb || 'unknown' },
    ];

    container.innerHTML = items.map(item => `
        <div class="health-item">
            <span class="label">${item.label}</span>
            <span class="health-badge ${item.status}">${item.status}</span>
        </div>
    `).join('');
}

// ═══ Market Insights ═══
function renderMarketInsights(data) {
    if (!data) return;

    // Top locations
    const locContainer = document.getElementById('topLocations');
    if (locContainer && data.top_locations?.length) {
        locContainer.innerHTML = data.top_locations.slice(0, 6).map(loc => `
            <div class="insight-item">
                <span class="name">📍 ${escapeHtml(loc.location)}</span>
                <span class="count">${loc.job_count} jobs</span>
            </div>
        `).join('');
    }

    // Top companies
    const compContainer = document.getElementById('topCompanies');
    if (compContainer && data.top_companies?.length) {
        compContainer.innerHTML = data.top_companies.slice(0, 6).map(comp => `
            <div class="insight-item">
                <span class="name">🏢 ${escapeHtml(comp.company)}</span>
                <span class="count">${comp.job_count} jobs</span>
            </div>
        `).join('');
    }

    // Salary insights
    const salaryContainer = document.getElementById('salaryInsights');
    if (salaryContainer && data.salary_insights) {
        const sal = data.salary_insights;
        salaryContainer.innerHTML = `
            <div class="insight-item">
                <span class="name">Avg Min Salary</span>
                <span class="count">₹${(sal.average_min_salary/100000).toFixed(1)}L</span>
            </div>
            <div class="insight-item">
                <span class="name">Avg Max Salary</span>
                <span class="count">₹${(sal.average_max_salary/100000).toFixed(1)}L</span>
            </div>
            <div class="insight-item">
                <span class="name">Jobs with Salary Data</span>
                <span class="count">${sal.jobs_with_salary}</span>
            </div>
        `;
    }
}

// ═══ Utilities ═══
function setTextContent(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
}

function formatNumber(n) {
    if (n >= 1000) return (n / 1000).toFixed(1) + 'K';
    return String(n);
}

function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
