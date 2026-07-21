// Paste your Colab backend URL here (e.g., https://xxxx.gradio.live)
const API_BASE = "https://xxxxx.gradio.live";

let mode = "image";
let currentMediaUrl = null;
let isGenerating = false;

// --- Tab switching ---
document.getElementById("tab-image").addEventListener("click", () => {
  if (isGenerating) return;
  mode = "image";
  document.getElementById("file-wrapper").style.display = "none";
  updateTabs();
});
document.getElementById("tab-video").addEventListener("click", () => {
  if (isGenerating) return;
  mode = "video";
  document.getElementById("file-wrapper").style.display = "none";
  updateTabs();
});
document.getElementById("tab-img2vid").addEventListener("click", () => {
  if (isGenerating) return;
  mode = "img2vid";
  document.getElementById("file-wrapper").style.display = "flex";
  updateTabs();
});

document.getElementById("image-upload").addEventListener("change", (e) => {
  const fileName = e.target.files[0]?.name || "";
  document.getElementById("file-name").textContent = fileName;
});

function updateTabs() {
  document.querySelectorAll(".tab").forEach(b => b.classList.remove("active"));
  document.getElementById(`tab-${mode}`).classList.add("active");
}

// Helper: convert file to base64
function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

// --- Generation ---
document.getElementById("generate-btn").addEventListener("click", async () => {
  if (isGenerating) return;

  const prompt = document.getElementById("prompt").value.trim();
  const fileInput = document.getElementById("image-upload");
  const loading = document.getElementById("loading");
  const outputCard = document.getElementById("output-card");
  const outputImg = document.getElementById("output-image");
  const outputVid = document.getElementById("output-video");
  const cardTitle = document.getElementById("card-title");
  const generateBtn = document.getElementById("generate-btn");

  // Reset UI
  outputImg.style.display = "none";
  outputVid.style.display = "none";
  outputCard.style.display = "none";
  loading.style.display = "flex";
  currentMediaUrl = null;
  isGenerating = true;
  generateBtn.disabled = true;
  generateBtn.style.opacity = "0.7";
  generateBtn.style.cursor = "not-allowed";

  try {
    let data = [];
    if (mode === "image") {
      data = ["image", prompt];
    } else if (mode === "video") {
      data = ["video", prompt];
    } else if (mode === "img2vid") {
      if (!fileInput.files[0]) throw new Error("Please select an image first.");
      const imageBase64 = await fileToBase64(fileInput.files[0]);
      data = ["img2vid", imageBase64, prompt];
    }

    const res = await fetch(`${API_BASE}/api/predict`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ data })
    });

    if (!res.ok) throw new Error(`API error ${res.status}`);
    const result = await res.json();
    const url = result.data[0];
    currentMediaUrl = url;

    if (mode === "image") {
      outputImg.src = url;
      outputImg.style.display = "block";
      cardTitle.textContent = "Generated Image";
    } else {
      outputVid.src = url;
      outputVid.style.display = "block";
      cardTitle.textContent = "Generated Video";
    }
    outputCard.style.display = "block";
  } catch (e) {
    alert("Generation failed: " + e.message);
    console.error(e);
  } finally {
    loading.style.display = "none";
    isGenerating = false;
    generateBtn.disabled = false;
    generateBtn.style.opacity = "1";
    generateBtn.style.cursor = "pointer";
  }
});

// --- Download (fixed SVG icon preservation) ---
document.getElementById("download-btn").addEventListener("click", async () => {
  if (!currentMediaUrl) return;
  const downloadBtn = document.getElementById("download-btn");
  const downloadText = document.getElementById("download-text");
  const originalText = downloadText.textContent;
  downloadText.textContent = "Saving...";
  downloadBtn.disabled = true;
  try {
    const response = await fetch(currentMediaUrl);
    const blob = await response.blob();
    const blobUrl = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = blobUrl;
    const ext = mode === "image" ? "png" : "mp4";
    a.download = `clipcraft-${Date.now()}.${ext}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(blobUrl);
  } catch (e) {
    alert("Download failed.");
  }
  downloadText.textContent = originalText;
  downloadBtn.disabled = false;
});
