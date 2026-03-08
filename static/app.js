/* ============================================================
   postify — Client-side logic
   ============================================================ */

document.addEventListener("DOMContentLoaded", () => {
    // ---- DOM references ----
    const promptInput = document.getElementById("promptInput");
    const platformSelect = document.getElementById("platformSelect");
    const countValue = document.getElementById("countValue");
    const countMinus = document.getElementById("countMinus");
    const countPlus = document.getElementById("countPlus");
    const btnText = document.getElementById("btnText");
    const btnImage = document.getElementById("btnImage");
    const styleControls = document.getElementById("styleControls");
    const gradientToggle = document.getElementById("gradientToggle");
    const gradientRow = document.getElementById("gradientRow");
    const fontSize = document.getElementById("fontSize");
    const fontSizeValue = document.getElementById("fontSizeValue");
    const textColor = document.getElementById("textColor");
    const alignment = document.getElementById("alignment");
    const bgColor = document.getElementById("bgColor");
    const gradientStart = document.getElementById("gradientStart");
    const gradientEnd = document.getElementById("gradientEnd");
    const imgWidth = document.getElementById("imgWidth");
    const imgHeight = document.getElementById("imgHeight");
    const bgImageUpload = document.getElementById("bgImageUpload");
    const fileUploadZone = document.getElementById("fileUploadZone");
    const fileName = document.getElementById("fileName");
    const generateBtn = document.getElementById("generateBtn");
    const emptyState = document.getElementById("emptyState");
    const carousel = document.getElementById("carousel");
    const carouselTrack = document.getElementById("carouselTrack");
    const carouselPrev = document.getElementById("carouselPrev");
    const carouselNext = document.getElementById("carouselNext");
    const carouselCounter = document.getElementById("carouselCounter");
    const downloadBtn = document.getElementById("downloadBtn");
    const copyBtn = document.getElementById("copyBtn");
    const loadingOverlay = document.getElementById("loadingOverlay");

    // Social media elements
    const publishSection = document.getElementById("publishSection");
    const publishLinkedin = document.getElementById("publishLinkedin");
    const publishFacebook = document.getElementById("publishFacebook");
    const publishInstagram = document.getElementById("publishInstagram");
    const connectLinkedin = document.getElementById("connectLinkedin");
    const connectFacebook = document.getElementById("connectFacebook");
    const connectInstagram = document.getElementById("connectInstagram");
    const statusLinkedin = document.getElementById("statusLinkedin");
    const statusFacebook = document.getElementById("statusFacebook");
    const statusInstagram = document.getElementById("statusInstagram");
    const accountLinkedin = document.getElementById("accountLinkedin");
    const accountFacebook = document.getElementById("accountFacebook");
    const accountInstagram = document.getElementById("accountInstagram");

    let postType = "text";
    let variationCount = 1;
    let currentSlide = 0;
    let slides = []; // {text, blob?}
    let connectedPlatforms = { linkedin: false, facebook: false, instagram: false };
    let hasGeneratedContent = false;

    // ---- Initialize ----
    fetchAuthStatus();
    checkAuthRedirect();

    // ---- Count selector ----
    countMinus.addEventListener("click", () => {
        variationCount = Math.max(1, variationCount - 1);
        countValue.textContent = variationCount;
    });
    countPlus.addEventListener("click", () => {
        variationCount = Math.min(10, variationCount + 1);
        countValue.textContent = variationCount;
    });

    // ---- Post type toggle ----
    btnText.addEventListener("click", () => switchType("text"));
    btnImage.addEventListener("click", () => switchType("image"));

    function switchType(type) {
        postType = type;
        btnText.classList.toggle("active", type === "text");
        btnImage.classList.toggle("active", type === "image");
        styleControls.classList.toggle("visible", type === "image");
    }

    // ---- Gradient toggle ----
    gradientToggle.addEventListener("change", () => {
        gradientRow.classList.toggle("visible", gradientToggle.checked);
    });

    // ---- Font size label ----
    fontSize.addEventListener("input", () => {
        fontSizeValue.textContent = `${fontSize.value}px`;
    });

    // ---- File upload ----
    fileUploadZone.addEventListener("click", () => bgImageUpload.click());
    fileUploadZone.addEventListener("dragover", (e) => { e.preventDefault(); fileUploadZone.style.borderColor = "var(--accent)"; });
    fileUploadZone.addEventListener("dragleave", () => { fileUploadZone.style.borderColor = ""; });
    fileUploadZone.addEventListener("drop", (e) => {
        e.preventDefault();
        fileUploadZone.style.borderColor = "";
        if (e.dataTransfer.files.length) {
            bgImageUpload.files = e.dataTransfer.files;
            fileName.textContent = e.dataTransfer.files[0].name;
        }
    });
    bgImageUpload.addEventListener("change", () => {
        fileName.textContent = bgImageUpload.files[0]?.name || "";
    });

    // ---- Generate ----
    generateBtn.addEventListener("click", async () => {
        const prompt = promptInput.value.trim();
        if (!prompt) { shakeButton(generateBtn); return; }

        showLoading(true);

        try {
            if (postType === "text") {
                await generateTextPost(prompt);
            } else {
                await generateImagePost(prompt);
            }
            hasGeneratedContent = true;
            updatePublishButtons();
        } catch (err) {
            console.error(err);
            alert("Generation failed — see console for details.");
        } finally {
            showLoading(false);
        }
    });

    // ---- Text post ----
    async function generateTextPost(prompt) {
        const formData = new FormData();
        formData.append("prompt", prompt);
        formData.append("platform", platformSelect.value);
        formData.append("count", variationCount);

        const res = await fetch("/api/generate", { method: "POST", body: formData });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        const platformLabel = platformSelect.options[platformSelect.selectedIndex].text;
        slides = data.variations.map(v => ({
            text: v.content,
            blob: null,
            meta: `🤖 ${data.model} · 🎯 ${platformLabel} · 📏 ${v.character_count} chars · 📄 ${v.line_count} line${v.line_count !== 1 ? "s" : ""}`,
        }));

        renderCarousel("text");
    }

    // ---- Image post ----
    async function generateImagePost(prompt) {
        const formData = new FormData();
        formData.append("prompt", prompt);
        formData.append("platform", platformSelect.value);
        formData.append("count", variationCount);
        formData.append("font_size", fontSize.value);
        formData.append("text_color", textColor.value);
        formData.append("alignment", alignment.value);
        formData.append("bg_color", bgColor.value);
        formData.append("gradient", gradientToggle.checked);
        formData.append("gradient_start", gradientStart.value);
        formData.append("gradient_end", gradientEnd.value);
        formData.append("width", imgWidth.value);
        formData.append("height", imgHeight.value);

        if (bgImageUpload.files.length) {
            formData.append("bg_image", bgImageUpload.files[0]);
        }

        const res = await fetch("/api/generate-image", { method: "POST", body: formData });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        slides = data.variations.map(v => {
            const bytes = Uint8Array.from(atob(v.image_b64), c => c.charCodeAt(0));
            const blob = new Blob([bytes], { type: "image/png" });
            return {
                text: v.text,
                blob: blob,
                imageUrl: URL.createObjectURL(blob),
            };
        });

        renderCarousel("image");
    }

    // =========================================================================
    //  Carousel
    // =========================================================================

    function renderCarousel(type) {
        currentSlide = 0;
        carouselTrack.innerHTML = "";

        slides.forEach((slide, i) => {
            const div = document.createElement("div");
            div.className = "carousel-slide";

            if (type === "text") {
                div.innerHTML = `
                    <div class="slide-text-card">${escapeHtml(slide.text)}</div>
                    <div class="slide-meta">${slide.meta}</div>
                `;
            } else {
                div.innerHTML = `
                    <div class="slide-image">
                        <img src="${slide.imageUrl}" alt="Post variation ${i + 1}">
                    </div>
                    <div class="slide-meta" style="margin-top:12px;">
                        <span style="white-space:pre-wrap;font-size:0.82rem;color:var(--text-muted);max-height:60px;overflow:auto;">${escapeHtml(slide.text).substring(0, 200)}${slide.text.length > 200 ? "…" : ""}</span>
                    </div>
                `;
            }

            carouselTrack.appendChild(div);
        });

        // Show/hide elements
        emptyState.style.display = "none";
        carousel.style.display = "block";
        downloadBtn.style.display = (type === "image") ? "flex" : "none";
        copyBtn.style.display = "flex";

        // Arrows
        carouselPrev.style.display = slides.length > 1 ? "flex" : "none";
        carouselNext.style.display = slides.length > 1 ? "flex" : "none";

        updateCarouselPosition();
        renderDots();
    }

    function updateCarouselPosition() {
        carouselTrack.style.transform = `translateX(-${currentSlide * 100}%)`;
        renderDots();
    }

    function renderDots() {
        carouselCounter.innerHTML = "";
        if (slides.length <= 1) return;

        slides.forEach((_, i) => {
            const dot = document.createElement("div");
            dot.className = `carousel-dot${i === currentSlide ? " active" : ""}`;
            dot.addEventListener("click", () => { currentSlide = i; updateCarouselPosition(); });
            carouselCounter.appendChild(dot);
        });
    }

    carouselPrev.addEventListener("click", () => {
        if (currentSlide > 0) { currentSlide--; updateCarouselPosition(); }
    });
    carouselNext.addEventListener("click", () => {
        if (currentSlide < slides.length - 1) { currentSlide++; updateCarouselPosition(); }
    });

    // Keyboard navigation
    document.addEventListener("keydown", (e) => {
        if (!slides.length) return;
        if (e.key === "ArrowLeft" && currentSlide > 0) { currentSlide--; updateCarouselPosition(); }
        if (e.key === "ArrowRight" && currentSlide < slides.length - 1) { currentSlide++; updateCarouselPosition(); }
    });

    // ---- Download current image ----
    downloadBtn.addEventListener("click", () => {
        const slide = slides[currentSlide];
        if (!slide?.blob) return;
        const url = URL.createObjectURL(slide.blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `postforge_v${currentSlide + 1}.png`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
    });

    // ---- Copy current text ----
    copyBtn.addEventListener("click", async () => {
        const text = slides[currentSlide]?.text;
        if (!text) return;
        try {
            await navigator.clipboard.writeText(text);
            const original = copyBtn.innerHTML;
            copyBtn.innerHTML = "<span>✅</span> Copied!";
            setTimeout(() => { copyBtn.innerHTML = original; }, 1500);
        } catch {
            const ta = document.createElement("textarea");
            ta.value = text;
            document.body.appendChild(ta);
            ta.select();
            document.execCommand("copy");
            ta.remove();
        }
    });

    // =========================================================================
    //  Social media — auth status, connect, publish
    // =========================================================================

    async function fetchAuthStatus() {
        try {
            const res = await fetch("/auth/status");
            const data = await res.json();
            connectedPlatforms = data;
            updateConnectionUI();
        } catch (err) {
            console.error("Could not fetch auth status:", err);
        }
    }

    function checkAuthRedirect() {
        const params = new URLSearchParams(window.location.search);
        if (params.get("auth_success")) {
            showToast(`✅ Connected to ${params.get("auth_success")}!`);
            fetchAuthStatus();
            window.history.replaceState({}, "", "/");
        }
        if (params.get("auth_error")) {
            showToast(`❌ Failed to connect to ${params.get("auth_error")}`, true);
            window.history.replaceState({}, "", "/");
        }
    }

    function updateConnectionUI() {
        updateAccountItem("linkedin", connectLinkedin, statusLinkedin, accountLinkedin);
        updateAccountItem("facebook", connectFacebook, statusFacebook, accountFacebook);
        updateAccountItem("instagram", connectInstagram, statusInstagram, accountInstagram);
        updatePublishButtons();
    }

    function updateAccountItem(platform, btn, dot, item) {
        const connected = connectedPlatforms[platform];
        dot.classList.toggle("connected", connected);
        item.classList.toggle("connected", connected);
        btn.textContent = connected ? "Disconnect" : "Connect";
        btn.classList.toggle("is-connected", connected);
    }

    function updatePublishButtons() {
        if (!hasGeneratedContent) { publishSection.style.display = "none"; return; }
        const anyConnected = connectedPlatforms.linkedin || connectedPlatforms.facebook || connectedPlatforms.instagram;
        publishSection.style.display = anyConnected ? "block" : "none";
        publishLinkedin.style.display = connectedPlatforms.linkedin ? "flex" : "none";
        publishFacebook.style.display = connectedPlatforms.facebook ? "flex" : "none";
        publishInstagram.style.display = connectedPlatforms.instagram ? "flex" : "none";
    }

    // ---- Connect / Disconnect ----
    connectLinkedin.addEventListener("click", () => handleConnect("linkedin"));
    connectFacebook.addEventListener("click", () => handleConnect("facebook"));
    connectInstagram.addEventListener("click", () => handleConnect("instagram"));

    async function handleConnect(platform) {
        if (connectedPlatforms[platform]) {
            await fetch(`/auth/${platform}/disconnect`, { method: "POST" });
            await fetchAuthStatus();
            showToast(`Disconnected from ${platform}`);
        } else {
            window.location.href = `/auth/${platform}/login`;
        }
    }

    // ---- Publish current slide ----
    publishLinkedin.addEventListener("click", () => handlePublish("linkedin"));
    publishFacebook.addEventListener("click", () => handlePublish("facebook"));
    publishInstagram.addEventListener("click", () => handlePublish("instagram"));

    async function handlePublish(platform) {
        const slide = slides[currentSlide];
        if (!slide) return;
        const btn = { linkedin: publishLinkedin, facebook: publishFacebook, instagram: publishInstagram }[platform];
        const originalHTML = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = "<span>⏳</span> Publishing…";

        try {
            const formData = new FormData();
            formData.append("platform", platform);
            formData.append("text", slide.text || "");
            if (slide.blob) formData.append("image", slide.blob, "post.png");

            const res = await fetch("/api/publish", { method: "POST", body: formData });
            const data = await res.json();

            if (data.success) {
                btn.innerHTML = "<span>✅</span> Published!";
                showToast(`✅ Published to ${platform}!`);
            } else {
                btn.innerHTML = "<span>❌</span> Failed";
                showToast(`❌ ${data.error || "Publishing failed"}`, true);
            }
            setTimeout(() => { btn.innerHTML = originalHTML; btn.disabled = false; }, 3000);
        } catch (err) {
            console.error(err);
            btn.innerHTML = originalHTML;
            btn.disabled = false;
            showToast("❌ Network error during publishing", true);
        }
    }

    // ---- Helpers ----
    function showLoading(on) {
        loadingOverlay.classList.toggle("active", on);
    }

    function shakeButton(el) {
        el.style.animation = "none";
        void el.offsetWidth;
        el.style.animation = "shake 0.4s ease";
        setTimeout(() => { el.style.animation = ""; }, 500);
    }

    function escapeHtml(str) {
        const div = document.createElement("div");
        div.textContent = str;
        return div.innerHTML;
    }

    function showToast(message, isError = false) {
        const toast = document.createElement("div");
        toast.style.cssText = `
            position: fixed; bottom: 24px; right: 24px; z-index: 1000;
            padding: 14px 24px; border-radius: 12px;
            background: ${isError ? "rgba(248,113,113,0.15)" : "rgba(52,211,153,0.15)"};
            border: 1px solid ${isError ? "#f87171" : "#34d399"};
            color: ${isError ? "#fca5a5" : "#6ee7b7"};
            font-family: var(--font); font-size: 0.88rem; font-weight: 600;
            backdrop-filter: blur(12px);
            animation: fadeSlideIn 0.3s ease;
        `;
        toast.textContent = message;
        document.body.appendChild(toast);
        setTimeout(() => {
            toast.style.opacity = "0";
            toast.style.transition = "opacity 0.3s ease";
            setTimeout(() => toast.remove(), 300);
        }, 3500);
    }
});

/* tiny shake keyframes injected via JS */
const shakeStyle = document.createElement("style");
shakeStyle.textContent = `
@keyframes shake {
  0%, 100% { transform: translateX(0); }
  25% { transform: translateX(-6px); }
  50% { transform: translateX(6px); }
  75% { transform: translateX(-4px); }
}`;
document.head.appendChild(shakeStyle);
