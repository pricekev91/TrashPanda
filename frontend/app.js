const jobsElement = document.getElementById('jobs');
const statusElement = document.getElementById('status-text');
const refreshButton = document.getElementById('refresh-button');
const totalMetricElement = document.getElementById('metric-total');
const appliedMetricElement = document.getElementById('metric-applied');
const ghostedMetricElement = document.getElementById('metric-ghosted');
const ghostedPercentElement = document.getElementById('metric-ghosted-percent');
const flightMetricElement = document.getElementById('metric-flight');
const flightWindowElement = document.getElementById('metric-flight-window');
const feedsMetricElement = document.getElementById('metric-feeds');
const ingestSummaryElement = document.getElementById('ingest-summary');
const searchInput = document.getElementById('search-input');
const statusFilter = document.getElementById('status-filter');
const windowFilter = document.getElementById('window-filter');

let allJobs = [];
let latestIngestState = null;
let latestDashboardSummary = null;

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

function updateMetrics(ingestState, dashboardSummary, jobs) {
  totalMetricElement.textContent = dashboardSummary?.total_jobs ?? jobs.length;
  appliedMetricElement.textContent = dashboardSummary?.applied_jobs ?? jobs.filter((job) => job.applied_at).length;
  ghostedMetricElement.textContent = dashboardSummary?.ghosted_jobs ?? 0;
  ghostedPercentElement.textContent = `${dashboardSummary?.ghosted_percent ?? 0}% of applied`;
  flightMetricElement.textContent = dashboardSummary?.in_flight_jobs ?? 0;
  flightWindowElement.textContent = `${dashboardSummary?.in_flight_window_days ?? windowFilter.value} day window`;
  feedsMetricElement.textContent = dashboardSummary?.feed_count ?? ingestState?.feed_count ?? 0;

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
  const statusValue = statusFilter.value;

  return allJobs.filter((job) => {
    const matchesQuery = !query || [job.title, job.company, job.summary, job.source, job.decision_reason || ''].join(' ').toLowerCase().includes(query);
    const matchesStatus =
      statusValue === 'all' ||
      (statusValue === 'active' && job.status !== 'not_interested') ||
      job.status === statusValue;
    return matchesQuery && matchesStatus;
  });
}

function formatAppliedDate(value) {
  if (!value) {
    return 'Not applied yet';
  }

  return new Date(value).toLocaleDateString();
}

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

async function updateJob(jobId, payload) {
  const response = await fetch(`/api/v1/jobs/${jobId}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(errorText || `Update failed with ${response.status}`);
  }

  return response.json();
}

async function handleMarkApplied(jobId) {
  const input = document.querySelector(`[data-applied-input="${jobId}"]`);
  const appliedDate = input?.value;
  if (!appliedDate) {
    statusElement.textContent = 'Choose an applied date before marking a job as applied.';
    return;
  }

  await updateJob(jobId, {
    status: 'applied',
    applied_at: new Date(`${appliedDate}T12:00:00Z`).toISOString(),
  });
  await loadJobs();
}

async function handleNotInterested(jobId) {
  const reasonInput = document.querySelector(`[data-reason-input="${jobId}"]`);
  const reason = reasonInput?.value?.trim();
  if (!reason) {
    statusElement.textContent = 'Not Interested requires a reason so TrashPanda can learn from it later.';
    return;
  }

  await updateJob(jobId, {
    status: 'not_interested',
    decision_reason: reason,
  });
  await loadJobs();
}

async function handleReturnToQueue(jobId) {
  await updateJob(jobId, {
    status: 'discovered',
  });
  await loadJobs();
}

function attachCardActions() {
  jobsElement.querySelectorAll('[data-action="apply"]').forEach((button) => {
    button.addEventListener('click', async () => {
      try {
        await handleMarkApplied(button.dataset.jobId);
      } catch (error) {
        statusElement.textContent = `Update failed: ${error.message}`;
      }
    });
  });

  jobsElement.querySelectorAll('[data-action="not-interested"]').forEach((button) => {
    button.addEventListener('click', async () => {
      try {
        await handleNotInterested(button.dataset.jobId);
      } catch (error) {
        statusElement.textContent = `Update failed: ${error.message}`;
      }
    });
  });

  jobsElement.querySelectorAll('[data-action="return"]').forEach((button) => {
    button.addEventListener('click', async () => {
      try {
        await handleReturnToQueue(button.dataset.jobId);
      } catch (error) {
        statusElement.textContent = `Update failed: ${error.message}`;
      }
    });
  });
}

function renderJobs(jobs) {
  jobsElement.innerHTML = '';

  if (!jobs.length) {
    jobsElement.innerHTML = '<div class="empty">No jobs matched the current filters.</div>';
    statusElement.textContent = 'API reachable, but nothing matches the current view.';
    return;
  }

  const appliedCount = jobs.filter((job) => job.status === 'applied').length;
  const notInterestedCount = jobs.filter((job) => job.status === 'not_interested').length;
  statusElement.textContent = `${jobs.length} jobs shown. ${appliedCount} applied. ${notInterestedCount} in the Not Interested bucket.`;

  jobs.forEach((job) => {
    const article = document.createElement('article');
    article.className = 'job-card';
    const sourceLink = job.source_url
      ? `<a class="job-link" href="${escapeHtml(job.source_url)}" target="_blank" rel="noreferrer">Open listing</a>`
      : '<span class="job-link muted-link">No source link</span>';
    const decisionReason = job.decision_reason
      ? `<p class="decision-reason"><strong>Why not interested:</strong> ${escapeHtml(job.decision_reason)}</p>`
      : '';
    const appliedValue = job.applied_at ? new Date(job.applied_at).toISOString().slice(0, 10) : '';
    article.innerHTML = `
      <div class="job-card-header">
        <div>
          <p class="job-company">${job.company}</p>
          <h3>${job.title}</h3>
        </div>
        <div class="score-pill">${job.score.toFixed(0)}</div>
      </div>
      <p class="job-meta">${job.location} · ${job.source} · ${job.status}</p>
      <p class="job-applied">Applied: ${formatAppliedDate(job.applied_at)}</p>
      <p class="job-summary">${job.summary}</p>
      ${decisionReason}
      <div class="job-actions-meta">${sourceLink}</div>
      <div class="job-actions">
        <label class="action-field">
          <span>Applied date</span>
          <input data-applied-input="${job.id}" type="date" value="${appliedValue}">
        </label>
        <button data-action="apply" data-job-id="${job.id}" type="button">Mark Applied</button>
      </div>
      <div class="job-actions job-actions-secondary">
        <label class="action-field action-field-wide">
          <span>Not Interested reason</span>
          <textarea data-reason-input="${job.id}" rows="2" placeholder="Explain why this role should be filtered out later.">${job.decision_reason || ''}</textarea>
        </label>
        <button data-action="not-interested" data-job-id="${job.id}" type="button">Move to Not Interested</button>
        <button class="button-secondary" data-action="return" data-job-id="${job.id}" type="button">Return to Queue</button>
      </div>
    `;
    jobsElement.appendChild(article);
  });

  attachCardActions();
}

function renderView() {
  updateMetrics(latestIngestState, latestDashboardSummary, allJobs);
  renderJobs(filteredJobs());
}

async function loadIngestState() {
  const response = await fetch('/api/v1/ingest-state');
  if (!response.ok) {
    throw new Error(`Ingest state returned ${response.status}`);
  }

  latestIngestState = await response.json();
}

async function loadDashboardSummary() {
  const response = await fetch(`/api/v1/dashboard-summary?in_flight_window_days=${windowFilter.value}`);
  if (!response.ok) {
    throw new Error(`Dashboard summary returned ${response.status}`);
  }

  latestDashboardSummary = await response.json();
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
    await loadDashboardSummary();
    renderView();
  } catch (error) {
    jobsElement.innerHTML = '<div class="empty">Dashboard could not reach the backend.</div>';
    statusElement.textContent = `Load failed: ${error.message}`;
    ingestSummaryElement.textContent = 'Ingest status unavailable.';
  }
}

refreshButton.addEventListener('click', loadJobs);
searchInput.addEventListener('input', renderView);
statusFilter.addEventListener('change', renderView);
windowFilter.addEventListener('change', loadJobs);
loadJobs();