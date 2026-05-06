const jobsElement = document.getElementById('jobs');
const statusElement = document.getElementById('status-text');
const refreshButton = document.getElementById('refresh-button');

function renderJobs(jobs) {
  jobsElement.innerHTML = '';

  if (!jobs.length) {
    jobsElement.innerHTML = '<div class="empty">No jobs found yet.</div>';
    statusElement.textContent = 'API reachable, but no jobs are stored yet.';
    return;
  }

  statusElement.textContent = `${jobs.length} jobs loaded from TrashPanda API.`;

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

async function loadJobs() {
  statusElement.textContent = 'Loading jobs from the API...';

  try {
    const response = await fetch('/api/v1/jobs');
    if (!response.ok) {
      throw new Error(`API returned ${response.status}`);
    }

    const jobs = await response.json();
    renderJobs(jobs);
  } catch (error) {
    jobsElement.innerHTML = '<div class="empty">Dashboard could not reach the backend.</div>';
    statusElement.textContent = `Load failed: ${error.message}`;
  }
}

refreshButton.addEventListener('click', loadJobs);
loadJobs();