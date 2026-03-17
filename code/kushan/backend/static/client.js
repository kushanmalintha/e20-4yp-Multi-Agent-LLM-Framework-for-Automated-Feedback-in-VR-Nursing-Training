async function postFormData(fd) {
  const resp = await fetch('/api/ask', { method: 'POST', body: fd });
  return resp.json();
}

document.getElementById('textForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const text = document.getElementById('userText').value;
  const scenario_id = document.getElementById('scenario_id').value;
  const fd = new FormData();
  fd.append('scenario_id', scenario_id);
  fd.append('text', text);
  const j = await postFormData(fd);
  document.getElementById('responseText').textContent = j.text || JSON.stringify(j);
  if (j.audio_base64) {
    const binary = atob(j.audio_base64);
    const len = binary.length;
    const bytes = new Uint8Array(len);
    for (let i = 0; i < len; i++) bytes[i] = binary.charCodeAt(i);
    const blob = new Blob([bytes], { type: 'audio/mpeg' });
    const url = URL.createObjectURL(blob);
    const player = document.getElementById('audioPlayer');
    player.src = url;
    player.play();
  }
});

document.getElementById('audioForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const f = document.getElementById('audioFile').files[0];
  const scenario_id = document.getElementById('scenario_id').value;
  if (!f) { alert("Choose an audio file"); return; }
  const fd = new FormData();
  fd.append('scenario_id', scenario_id);
  fd.append('audio', f);
  const j = await postFormData(fd);
  document.getElementById('responseText').textContent = j.text || JSON.stringify(j);
  if (j.audio_base64) {
    const binary = atob(j.audio_base64);
    const len = binary.length;
    const bytes = new Uint8Array(len);
    for (let i = 0; i < len; i++) bytes[i] = binary.charCodeAt(i);
    const blob = new Blob([bytes], { type: 'audio/mpeg' });
    const url = URL.createObjectURL(blob);
    const player = document.getElementById('audioPlayer');
    player.src = url;
    player.play();
  }
});
