const jobsElement = document.getElementById('jobs');
const statusElement = document.getElementById('status-text');
const refreshButton = document.getElementById('refresh-button');
const totalMetricElement = document.getElementById('metric-total');
const remoteMetricElement = document.getElementById('metric-remote');
const unknownMetricElement = document.getElementById('metric-unknown');
const ingestSummaryElement = document.getElementById('ingest-summary');
const searchInput = document.getElementById('search-input');
const locationFilter = document.getElementById('location-filter');

let allJobs = [];
let latestIngestState = null;

function formatRelativeTime(value) {
  if (!value) {
    return 'No ingest timestamp yet.';
  }

  const timestamp = new Date(value);
  const diffMinutes = Math.max(0, Math.round((Date.now() - timestamp.getTime()) / 60000));
  if (diffMinutes < 1) {
    return 'updated just now';
  }
  if (diffMinutes < 60) {
    return `updated ${diffMinutes}m ago`;
  }

  const diffHours = Math.round(diffMinutes / 60);
  return `updated ${diffHours}h ago`;
}

function updateMetrics(ingestState, jobs) {
  totalMetricElement.textContent = ingestState?.total_jobs ?? jobs.length;
  remoteMetricElement.textContent = ingestState?.remote_jobs ?? jobs.filter((job) => job.location === 'Remote').length;
  unknownMetricElement.textContent = ingestState?.unknown_company_jobs ?? jobs.filter((job) => job.company === 'Unknown company').length;

  if (!ingestState) {
    ingestSummaryElement.textContent = 'Ingest status unavailable.';
    return;
  }

  const sourceSummary = ingestState.sources.map((source) => `${source.name}: +${source.inserted}`).join(' · ') || 'No sources reported';
  const errorSummary = ingestState.errors.length ? `Errors: ${ingestState.errors.join(' | ')}` : 'No ingest errors';
  ingestSummaryElement.textContent = `${sourceSummary} · ${formatRelativeTime(ingestState.updated_at)} · ${errorSummary}`;
}

function filteredJobs() {
  const query = searchInput.value.trim().toLowerCase();
  const locationValue = locationFilter.value;

  return allJobs.filter((job) => {
    const matchesQuery = !query || [job.title, job.company, job.summary, job.source].join(' ').toLowerCase().includes(query);
    const matchesLocation = locationValue === 'all' || job.location === locationValue;
    return matchesQuery && matchesLocation;
  });
}

function renderJobs(jobs) {
  jobsElement.innerHTML = '';

  if (!jobs.length) {
    jobsElement.innerHTML = '<div class="empty">No jobs matched the current filters.</div>';
    statusElement.textContent = 'API reachable, but nothing matches the current view.';
    return;
  }

  const unknownCompanies = jobs.filter((job) => job.company === 'Unknown company').length;
  statusElement.textContent = `${jobs.length} jobs shown. ${unknownCompanies} still need better company parsing.`;

  jobs.forEach((job) => {
    const article = document.createElement('article');
    article.className = 'job-card';
    article.innerHTML = `
      <div class="job-card-header">
        <div>
          <p class="job-company">${job.company}</p>
          <h3>${job.title}</h3>
        </div>
        <div class="score-pill">${job.score.toFixed(0)}</div>
      </div>
      <p class="job-meta">${job.location} · ${job.source} · ${job.status}</p>
      <p class="job-summary">${job.summary}</p>
    `;
    jobsElement.appendChild(article);
  });
}

function renderView() {
  updateMetrics(latestIngestState, allJobs);
  renderJobs(filteredJobs());
}

async function loadIngestState() {
  const response = await fetch('/api/v1/ingest-state');
  if (!response.ok) {
    throw new Error(`Ingest state returned ${response.status}`);
  }

  latestIngestState = await response.json();
}

async function loadJobs() {
  statusElement.textContent = 'Loading jobs from the API...';

  try {
    const jobsResponse = await fetch('/api/v1/jobs');
    if (!jobsResponse.ok) {
      throw new Error(`Jobs API returned ${jobsResponse.status}`);
    }

    allJobs = await jobsResponse.json();
    await loadIngestState();
    renderView();
  } catch (error) {
    jobsElement.innerHTML = '<div class="empty">Dashboard could not reach the backend.</div>';
    statusElement.textContent = `Load failed: ${error.message}`;
    ingestSummaryElement.textContent = 'Ingest status unavailable.';
  }
}

refreshButton.addEventListener('click', loadJobs);
searchInput.addEventListener('input', renderView);
locationFilter.addEventListener('change', renderView);
loadJobs();