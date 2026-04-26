// scope-creep control room — live SSE consumer

const AGENTS = ["Dr. Hong", "Andrey", "Dimitar"];

const elapsedEl   = document.getElementById("elapsed");
const eventCountEl = document.getElementById("event-count");
const runStateEl  = document.getElementById("run-state");
const connectionEl = document.getElementById("connection");

let startTime = null;
let eventCount = 0;
let elapsedTimer = null;

function pad(n) { return n.toString().padStart(2, "0"); }

function formatElapsed(seconds) {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${pad(m)}:${pad(s)}`;
}

function formatTime(ts) {
  const d = new Date(ts * 1000);
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

function setRunState(state) {
  runStateEl.textContent = state;
  runStateEl.dataset.state = state;
}

function startElapsed() {
  if (elapsedTimer) return;
  startTime = startTime || Date.now() / 1000;
  elapsedTimer = setInterval(() => {
    elapsedEl.textContent = formatElapsed(Date.now() / 1000 - startTime);
  }, 250);
}

function stopElapsed() {
  if (elapsedTimer) clearInterval(elapsedTimer);
  elapsedTimer = null;
}

function clearPlaceholder(laneEvents) {
  const ph = laneEvents.querySelector(".lane-empty");
  if (ph) ph.remove();
}

function appendEvent(event) {
  const agent = event.agent;
  const laneEvents = document.getElementById(`events-${agent}`);
  if (!laneEvents) return;

  clearPlaceholder(laneEvents);

  const node = document.createElement("div");
  node.className = "event";
  node.dataset.kind = event.kind;

  const meta = document.createElement("div");
  meta.className = "event-meta";

  const time = document.createElement("span");
  time.className = "event-time";
  time.textContent = formatTime(event.timestamp);

  const kind = document.createElement("span");
  kind.className = "event-kind";
  kind.textContent = event.kind;

  meta.append(time, kind);

  const content = document.createElement("div");
  content.className = "event-content";
  content.textContent = event.content;

  node.append(meta, content);
  laneEvents.appendChild(node);

  // auto-scroll to keep the latest event in view
  laneEvents.scrollTop = laneEvents.scrollHeight;

  // update phase indicator if present
  if (event.phase) {
    const phaseEl = document.getElementById(`phase-${agent}`);
    if (phaseEl) phaseEl.textContent = event.phase;
  }

  eventCount += 1;
  eventCountEl.textContent = eventCount;
}

function showPlaceholders() {
  AGENTS.forEach(agent => {
    const lane = document.getElementById(`events-${agent}`);
    if (lane && !lane.querySelector(".event")) {
      const ph = document.createElement("div");
      ph.className = "lane-empty";
      ph.textContent = "(awaiting events)";
      lane.appendChild(ph);
    }
  });
}

function connect() {
  setRunState("connecting");
  connectionEl.textContent = "● connecting to /events";
  connectionEl.className = "footer-r";

  const source = new EventSource("/events");

  source.addEventListener("open", () => {
    setRunState("running");
    connectionEl.textContent = "● live · /events";
    connectionEl.className = "footer-r connected";
    startElapsed();
  });

  source.addEventListener("event", (e) => {
    try {
      const event = JSON.parse(e.data);
      appendEvent(event);
    } catch (err) {
      console.error("bad event", err);
    }
  });

  source.addEventListener("heartbeat", () => {
    // keepalive — no-op
  });

  source.addEventListener("done", (e) => {
    setRunState("done");
    connectionEl.textContent = "● run complete";
    stopElapsed();
    source.close();
  });

  source.addEventListener("error", () => {
    if (source.readyState === EventSource.CLOSED) {
      setRunState("error");
      connectionEl.textContent = "● disconnected";
      connectionEl.className = "footer-r disconnected";
    }
  });
}

showPlaceholders();
connect();
