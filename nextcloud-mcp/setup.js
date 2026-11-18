const form = document.querySelector('form');
const status = document.querySelector('#status');
const feedback = document.querySelector('#feedback');
const submit = form.querySelector('button');
const reveal = document.querySelector('#reveal');
let csrf;
fetch('status').then(response => {
  if (!response.ok) throw new Error();
  return response.json();
}).then(data => {
  csrf = data.csrf;
  status.textContent = data.message;
  submit.disabled = false;
  reveal.disabled = false;
}).catch(() => { status.textContent = 'Cannot load setup. Reload the page.'; });
form.addEventListener('submit', async event => {
  event.preventDefault();
  submit.disabled = true;
  const data = Object.fromEntries(new FormData(form));
  form.elements.nextcloud_password.value = '';
  feedback.hidden = false;
  feedback.textContent = 'Testing connection…';
  try {
    const response = await fetch('connection', {
      method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Setup-CSRF': csrf },
      body: JSON.stringify(data),
    });
    const result = await response.json();
    feedback.textContent = result.message;
    if (response.ok) {
      form.reset();
      status.textContent = 'Restart the app to activate the saved connection.';
    }
  } catch { feedback.textContent = 'Request failed. Reload to check status before retrying.'; }
  finally { delete data.nextcloud_password; submit.disabled = false; }
});
reveal.addEventListener('click', async () => {
  const input = document.querySelector('#token');
  if (!input.hidden) {
    input.value = '';
    input.hidden = true;
    reveal.textContent = 'Show MCP token';
    return;
  }
  try {
    const response = await fetch('mcp-token', { method: 'POST', headers: { 'X-Setup-CSRF': csrf } });
    if (!response.ok) throw new Error();
    input.value = (await response.json()).token;
    input.type = 'text';
    input.hidden = false;
    input.select();
    reveal.textContent = 'Hide MCP token';
  } catch { feedback.hidden = false; feedback.textContent = 'Cannot retrieve token. Reload setup.'; }
});
