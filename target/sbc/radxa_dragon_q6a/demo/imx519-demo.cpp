// SPDX-License-Identifier: MIT
// IMX519 preview with isolated outlier correction and adaptive shadow denoising.
// Adapted from camera_ar0234; see LICENSE.MIT and sources.json.
#include <libcamera/libcamera.h>
#include <libcamera/formats.h>
#include <SDL2/SDL.h>
#include <GLES3/gl3.h>
#include <linux/dma-buf.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <algorithm>
#include <atomic>
#include <chrono>
#include <cmath>
#include <condition_variable>
#include <cstdio>
#include <csignal>
#include <cstring>
#include <deque>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <map>
#include <memory>
#include <mutex>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>

using namespace libcamera;
using Clock = std::chrono::steady_clock;
static volatile std::sig_atomic_t interrupted = 0;
static void signalHandler(int) { interrupted = 1; }
static void require(bool good, const std::string &message)
{
    if (!good) throw std::runtime_error(message);
}

class Capture {
    struct Mapping { void *base; size_t length; uint8_t *data; int fd; };
    CameraManager manager_;
    std::shared_ptr<Camera> camera_;
    std::unique_ptr<CameraConfiguration> config_;
    std::unique_ptr<FrameBufferAllocator> allocator_;
    std::vector<std::unique_ptr<Request>> requests_;
    std::map<FrameBuffer *, Mapping> mappings_;
    std::mutex mutex_;
    std::condition_variable ready_;
    std::deque<Request *> complete_;
    std::atomic<bool> stopping_{false};
    bool acquired_ = false, running_ = false;

    void requestComplete(Request *request)
    {
        if (stopping_ || request->status() == Request::RequestCancelled) return;
        std::lock_guard<std::mutex> lock(mutex_);
        complete_.push_back(request);
        ready_.notify_one();
    }

public:
    unsigned width = 0, height = 0, stride = 0;
    unsigned dropped = 0, errors = 0;
    ~Capture() { stop(); }

    void start(unsigned wantedWidth, unsigned wantedHeight, const std::string &cameraId)
    {
        require(manager_.start() == 0, "Cannot start libcamera");
        for (auto &candidate : manager_.cameras()) {
            if (candidate->id().find("imx519") != std::string::npos) {
                if (!cameraId.empty() && candidate->id() != cameraId) continue;
                require(!camera_, "Multiple IMX519 cameras found. Select an exact ID with --camera=ID; use --list-cameras.");
                camera_ = candidate;
            }
        }
        require(bool(camera_), cameraId.empty() ? "IMX519 not found. Check the driver and enabled port overlay." : "Requested IMX519 camera ID not found");
        std::cout << "CAMERA " << camera_->id() << std::endl;
        require(camera_->acquire() == 0, "Camera in use. Close the other preview first.");
        acquired_ = true;
        config_ = camera_->generateConfiguration({ StreamRole::VideoRecording });
        require(config_ && !config_->empty(), "Cannot generate camera configuration");
        auto &cfg = config_->at(0);
        cfg.size = Size(wantedWidth, wantedHeight);
        cfg.pixelFormat = formats::XBGR8888;
        cfg.bufferCount = 6;
        require(config_->validate() != CameraConfiguration::Invalid, "Invalid stream format");
        require(cfg.pixelFormat == formats::XBGR8888, "Expected RGBX output");
        require(camera_->configure(config_.get()) == 0, "Cannot configure camera");
        width = cfg.size.width;
        height = cfg.size.height;
        stride = cfg.stride;
        require(stride >= width * 4 && stride % 4 == 0, "Unexpected RGB stride");
        std::cout << "STREAM " << width << 'x' << height << " stride=" << stride << std::endl;
        allocator_ = std::make_unique<FrameBufferAllocator>(camera_);
        require(allocator_->allocate(cfg.stream()) >= 0, "Cannot allocate camera buffers");
        for (auto &buffer : allocator_->buffers(cfg.stream())) {
            require(buffer->planes().size() == 1, "Expected one RGBX plane");
            const auto plane = buffer->planes()[0];
            require(plane.offset != FrameBuffer::Plane::kInvalidOffset, "Invalid plane offset");
            require(plane.length >= stride * height, "Buffer is too small");
            size_t length = size_t(plane.offset) + plane.length;
            void *memory = mmap(nullptr, length, PROT_READ, MAP_SHARED, plane.fd.get(), 0);
            require(memory != MAP_FAILED, "Cannot map camera buffer");
            mappings_[buffer.get()] = {memory, length, static_cast<uint8_t *>(memory) + plane.offset, plane.fd.get()};
            auto request = camera_->createRequest();
            require(bool(request), "Cannot create capture request");
            require(request->addBuffer(cfg.stream(), buffer.get()) == 0, "Cannot add capture buffer");
            requests_.push_back(std::move(request));
        }
        camera_->requestCompleted.connect(this, &Capture::requestComplete);
    }
    void begin()
    {
        require(camera_->start() == 0, "Cannot start capture");
        running_ = true;
        for (auto &request : requests_)
            require(camera_->queueRequest(request.get()) == 0, "Cannot queue capture request");
    }

    Request *next()
    {
        std::unique_lock<std::mutex> lock(mutex_);
        ready_.wait_for(lock, std::chrono::milliseconds(20), [&] { return !complete_.empty(); });
        if (complete_.empty()) return nullptr;
        // Prefer a current frame if rendering ever falls behind.
        while (complete_.size() > 1) {
            Request *old = complete_.front();
            complete_.pop_front();
            lock.unlock();
            recycle(old);
            ++dropped;
            lock.lock();
        }
        Request *result = complete_.front();
        complete_.pop_front();
        return result;
    }

    FrameBuffer *buffer(Request *request) { return request->buffers().begin()->second; }
    const uint8_t *beginRead(Request *request)
    {
        auto &mapping = mappings_.at(buffer(request));
        dma_buf_sync sync{DMA_BUF_SYNC_START | DMA_BUF_SYNC_READ};
        require(ioctl(mapping.fd, DMA_BUF_IOCTL_SYNC, &sync) == 0, "Cannot synchronize DMA buffer for reading");
        return mapping.data;
    }
    void endRead(Request *request)
    {
        auto &mapping = mappings_.at(buffer(request));
        dma_buf_sync sync{DMA_BUF_SYNC_END | DMA_BUF_SYNC_READ};
        require(ioctl(mapping.fd, DMA_BUF_IOCTL_SYNC, &sync) == 0, "Cannot finish DMA buffer read");
    }
    void recycle(Request *request)
    {
        request->reuse(Request::ReuseBuffers);
        require(camera_->queueRequest(request) == 0, "Cannot requeue capture buffer");
    }
    void stop()
    {
        stopping_ = true;
        if (running_) { camera_->stop(); running_ = false; }
        if (camera_) camera_->requestCompleted.disconnect(this);
        complete_.clear();
        requests_.clear();
        for (auto &item : mappings_) munmap(item.second.base, item.second.length);
        mappings_.clear();
        allocator_.reset();
        if (acquired_) { camera_->release(); acquired_ = false; }
        config_.reset();
        camera_.reset();
        manager_.stop();
    }
};

static const char *vertexShader = R"GLSL(#version 300 es
out vec2 uv;
void main() {
    vec2 p = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2);
    uv = p;
    gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);
}
)GLSL";

static const char *denoiseShader = R"GLSL(#version 300 es
precision highp float;
in vec2 uv;
out vec4 outputColor;
uniform sampler2D sourceFrame;
uniform sampler2D historyFrame;
uniform vec2 pixelSize;
uniform float historyWeight;
uniform float spatialAmount;
uniform float colorSigma;
uniform float motionThreshold;
uniform bool historyReady;
void order(inout vec3 a, inout vec3 b) {
    vec3 low = min(a, b);
    b = max(a, b);
    a = low;
}
void main() {
    vec3 center = texture(sourceFrame, uv).rgb;
    // A two-pixel ring reaches beyond the small cross left by a hot Bayer site.
    // Sort each channel separately; the inner range protects edges and lines
    // supported by at least two surrounding samples. This is RGB correction,
    // not a calibrated sensor defect map.
    vec3 ring[8];
    ring[0] = texture(sourceFrame, uv + pixelSize * vec2(-2.0, -2.0)).rgb;
    ring[1] = texture(sourceFrame, uv + pixelSize * vec2( 0.0, -2.0)).rgb;
    ring[2] = texture(sourceFrame, uv + pixelSize * vec2( 2.0, -2.0)).rgb;
    ring[3] = texture(sourceFrame, uv + pixelSize * vec2(-2.0,  0.0)).rgb;
    ring[4] = texture(sourceFrame, uv + pixelSize * vec2( 2.0,  0.0)).rgb;
    ring[5] = texture(sourceFrame, uv + pixelSize * vec2(-2.0,  2.0)).rgb;
    ring[6] = texture(sourceFrame, uv + pixelSize * vec2( 0.0,  2.0)).rgb;
    ring[7] = texture(sourceFrame, uv + pixelSize * vec2( 2.0,  2.0)).rgb;
    order(ring[0], ring[1]); order(ring[2], ring[3]);
    order(ring[4], ring[5]); order(ring[6], ring[7]);
    order(ring[0], ring[2]); order(ring[1], ring[3]);
    order(ring[4], ring[6]); order(ring[5], ring[7]);
    order(ring[1], ring[2]); order(ring[5], ring[6]);
    order(ring[0], ring[4]); order(ring[3], ring[7]);
    order(ring[1], ring[5]); order(ring[2], ring[6]);
    order(ring[1], ring[4]); order(ring[3], ring[6]);
    order(ring[2], ring[4]); order(ring[3], ring[5]);
    order(ring[3], ring[4]);
    vec3 median = (ring[3] + ring[4]) * 0.5;
    vec3 outlierThreshold = max(vec3(0.12), (ring[6] - ring[1]) * 2.5 + 0.04);
    center = mix(center, median, step(outlierThreshold, center - median));
    float shadows = 1.0 - smoothstep(0.06, 0.22, dot(center, vec3(0.299, 0.587, 0.114)));
    // Color speckles can stay fixed across frames. Use the wider robust ring
    // for chroma as well, preserving center luminance and strong color edges.
    vec3 reference = (ring[2] + ring[3] + ring[4] + ring[5]) * 0.25;
    vec3 spread = ring[6] - ring[1];
    float colorEdge = max(spread.r, max(spread.g, spread.b));
    float chromaAmount = shadows * (0.45 + spatialAmount * 0.5) *
                         (1.0 - smoothstep(0.06, 0.20, colorEdge));
    float centerLuma = dot(center, vec3(0.299, 0.587, 0.114));
    float referenceLuma = dot(reference, vec3(0.299, 0.587, 0.114));
    center = mix(center, reference + vec3(centerLuma - referenceLuma), chromaAmount);
    float spatialStrength = mix(spatialAmount, min(spatialAmount + 0.48, 0.90), shadows);
    float temporalStrength = mix(historyWeight, min(historyWeight + 0.24, 0.94), shadows);
    float sigma = mix(colorSigma, colorSigma * 1.8, shadows);
    vec3 neighbors[4];
    neighbors[0] = texture(sourceFrame, uv + vec2(pixelSize.x, 0.0)).rgb;
    neighbors[1] = texture(sourceFrame, uv - vec2(pixelSize.x, 0.0)).rgb;
    neighbors[2] = texture(sourceFrame, uv + vec2(0.0, pixelSize.y)).rgb;
    neighbors[3] = texture(sourceFrame, uv - vec2(0.0, pixelSize.y)).rgb;
    vec3 spatial = center * 2.0;
    float totalWeight = 2.0;
    vec3 localMean = center * 4.0;
    vec3 low = center, high = center;
    for (int i = 0; i < 4; ++i) {
        vec3 difference = neighbors[i] - center;
        float w = 1.0 / (1.0 + dot(difference, difference) / (sigma * sigma));
        spatial += neighbors[i] * w;
        totalWeight += w;
        localMean += neighbors[i];
        low = min(low, neighbors[i]);
        high = max(high, neighbors[i]);
    }
    localMean *= 0.125;
    vec3 current = mix(center, spatial / totalWeight, spatialStrength);
    if (historyReady) {
        vec3 previous = texture(historyFrame, uv).rgb;
        vec3 oldMean = previous * 4.0;
        oldMean += texture(historyFrame, uv + vec2(pixelSize.x, 0.0)).rgb;
        oldMean += texture(historyFrame, uv - vec2(pixelSize.x, 0.0)).rgb;
        oldMean += texture(historyFrame, uv + vec2(0.0, pixelSize.y)).rgb;
        oldMean += texture(historyFrame, uv - vec2(0.0, pixelSize.y)).rgb;
        oldMean *= 0.125;
        float movement = length(localMean - oldMean);
        float threshold = mix(motionThreshold, motionThreshold * 0.55, shadows);
        float confidence = 1.0 - smoothstep(threshold, threshold * 2.2, movement);
        // Clamp history to the current neighborhood to limit trailing edges.
        previous = clamp(previous, low - 0.012, high + 0.012);
        current = mix(current, previous, temporalStrength * confidence);
    }
    outputColor = vec4(current, 1.0);
}
)GLSL";

static const char *displayShader = R"GLSL(#version 300 es
precision highp float;
in vec2 uv;
out vec4 outputColor;
uniform sampler2D sourceFrame;
uniform sampler2D filteredFrame;
uniform bool enabled;
uniform bool compare;
uniform float dividerWidth;
void main() {
    vec2 p = vec2(uv.x, 1.0 - uv.y);
    bool showSource = !enabled || (compare && uv.x < 0.5);
    outputColor = vec4(showSource ? texture(sourceFrame, p).rgb : texture(filteredFrame, p).rgb, 1.0);
    if (compare && abs(uv.x - 0.5) < dividerWidth) outputColor = vec4(1.0);
}
)GLSL";

class Renderer {
    SDL_Window *window_ = nullptr;
    SDL_GLContext context_ = nullptr;
    GLuint programs_[2]{}, textures_[3]{}, framebuffer_ = 0, vao_ = 0;
    int history_ = 0;
    bool historyReady_ = false;
    unsigned width_, height_;
    double lastFps_ = 0.0;

    static GLuint compile(GLenum kind, const char *source)
    {
        GLuint shader = glCreateShader(kind);
        glShaderSource(shader, 1, &source, nullptr);
        glCompileShader(shader);
        GLint ok = 0;
        glGetShaderiv(shader, GL_COMPILE_STATUS, &ok);
        if (!ok) {
            char message[4096];
            glGetShaderInfoLog(shader, sizeof(message), nullptr, message);
            glDeleteShader(shader);
            throw std::runtime_error(std::string("Shader: ") + message);
        }
        return shader;
    }
    static GLuint program(const char *fragment)
    {
        GLuint vs = compile(GL_VERTEX_SHADER, vertexShader);
        GLuint fs = compile(GL_FRAGMENT_SHADER, fragment);
        GLuint result = glCreateProgram();
        glAttachShader(result, vs); glAttachShader(result, fs);
        glLinkProgram(result);
        glDeleteShader(vs); glDeleteShader(fs);
        GLint ok = 0; glGetProgramiv(result, GL_LINK_STATUS, &ok);
        require(ok, "Cannot link shader program");
        return result;
    }
    void texture(int unit, GLuint texture)
    {
        glActiveTexture(GL_TEXTURE0 + unit);
        glBindTexture(GL_TEXTURE_2D, texture);
    }

public:
    bool enabled = true, compare = false;
    int strength = 1;
    void resetHistory() { historyReady_ = false; }
    Renderer(unsigned width, unsigned height, bool hidden = false) : width_(width), height_(height)
    {
        require(SDL_Init(SDL_INIT_VIDEO) == 0, SDL_GetError());
        SDL_GL_SetAttribute(SDL_GL_CONTEXT_PROFILE_MASK, SDL_GL_CONTEXT_PROFILE_ES);
        SDL_GL_SetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION, 3);
        SDL_GL_SetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, 0);
        SDL_GL_SetAttribute(SDL_GL_DOUBLEBUFFER, 1);
        unsigned flags = SDL_WINDOW_OPENGL | SDL_WINDOW_RESIZABLE | SDL_WINDOW_ALLOW_HIGHDPI;
        if (hidden) flags |= SDL_WINDOW_HIDDEN;
        unsigned windowWidth = std::min(width, 1600U);
        unsigned windowHeight = windowWidth * height / width;
        window_ = SDL_CreateWindow("IMX519", SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED,
                                   windowWidth, windowHeight, flags);
        require(window_, SDL_GetError());
        context_ = SDL_GL_CreateContext(window_);
        require(context_, SDL_GetError());
        SDL_GL_SetSwapInterval(0);
        std::cout << "GPU " << glGetString(GL_RENDERER) << " | " << glGetString(GL_VERSION) << std::endl;
        programs_[0] = program(denoiseShader);
        programs_[1] = program(displayShader);
        glGenVertexArrays(1, &vao_); glBindVertexArray(vao_);
        glGenFramebuffers(1, &framebuffer_);
        glGenTextures(3, textures_);
        for (GLuint t : textures_) {
            texture(0, t);
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
            // Keep temporal accumulation above 8-bit precision. Strong feedback
            // in RGBA8 otherwise rounds small updates away and freezes grain.
            glTexStorage2D(GL_TEXTURE_2D, 1, t == textures_[0] ? GL_RGBA8 : GL_RGBA16F, width_, height_);
        }
        updateTitle(0.0);
    }
    ~Renderer()
    {
        if (context_) {
            glDeleteTextures(3, textures_);
            glDeleteFramebuffers(1, &framebuffer_);
            glDeleteVertexArrays(1, &vao_);
            for (GLuint p : programs_) if (p) glDeleteProgram(p);
            SDL_GL_DeleteContext(context_);
        }
        if (window_) SDL_DestroyWindow(window_);
        SDL_Quit();
    }
    void updateTitle(double fps)
    {
        if (fps > 0.0) lastFps_ = fps;
        const char *names[] = {"", "Low", "Medium", "Strong"};
        std::string mode = !enabled ? "Original" : compare ? "Left: original | Right: denoised" : std::string(names[strength]) + " noise reduction";
        char title[256];
        std::snprintf(title, sizeof(title), "IMX519 %ux%u | %s | %.1f fps | N: on/off  C: compare  1-3: strength  F: fullscreen  Esc: close",
                      width_, height_, mode.c_str(), lastFps_);
        SDL_SetWindowTitle(window_, title);
    }
    bool events()
    {
        SDL_Event event;
        while (SDL_PollEvent(&event)) {
            if (event.type == SDL_QUIT) return false;
            if (event.type != SDL_KEYDOWN || event.key.repeat) continue;
            auto key = event.key.keysym.scancode;
            if (key == SDL_SCANCODE_ESCAPE || key == SDL_SCANCODE_Q) return false;
            if (key == SDL_SCANCODE_N || key == SDL_SCANCODE_0) { enabled = !enabled; compare = false; }
            if (key == SDL_SCANCODE_C) { compare = !compare; enabled = true; }
            if (key >= SDL_SCANCODE_1 && key <= SDL_SCANCODE_3) {
                strength = int(key - SDL_SCANCODE_1) + 1; enabled = true;
            }
            if (key == SDL_SCANCODE_F) {
                bool full = SDL_GetWindowFlags(window_) & SDL_WINDOW_FULLSCREEN_DESKTOP;
                SDL_SetWindowFullscreen(window_, full ? 0 : SDL_WINDOW_FULLSCREEN_DESKTOP);
            }
            updateTitle(0.0);
        }
        return true;
    }
    void process(const uint8_t *pixels, unsigned stride)
    {
        texture(0, textures_[0]);
        glPixelStorei(GL_UNPACK_ALIGNMENT, 4);
        glPixelStorei(GL_UNPACK_ROW_LENGTH, stride / 4);
        glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, width_, height_, GL_RGBA, GL_UNSIGNED_BYTE, pixels);
        glPixelStorei(GL_UNPACK_ROW_LENGTH, 0);
        int next = 1 - history_;
        glBindFramebuffer(GL_FRAMEBUFFER, framebuffer_);
        glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, textures_[1 + next], 0);
        require(glCheckFramebufferStatus(GL_FRAMEBUFFER) == GL_FRAMEBUFFER_COMPLETE, "Incomplete denoise framebuffer");
        glViewport(0, 0, width_, height_);
        glUseProgram(programs_[0]);
        texture(0, textures_[0]); texture(1, textures_[1 + history_]);
        auto p = programs_[0];
        glUniform1i(glGetUniformLocation(p, "sourceFrame"), 0);
        glUniform1i(glGetUniformLocation(p, "historyFrame"), 1);
        glUniform2f(glGetUniformLocation(p, "pixelSize"), 1.0f / width_, 1.0f / height_);
        const float weights[] = {0.0f, 0.60f, 0.75f, 0.86f};
        const float spatial[] = {0.0f, 0.18f, 0.32f, 0.48f};
        glUniform1f(glGetUniformLocation(p, "historyWeight"), weights[strength]);
        glUniform1f(glGetUniformLocation(p, "spatialAmount"), spatial[strength]);
        glUniform1f(glGetUniformLocation(p, "colorSigma"), 0.050f);
        glUniform1f(glGetUniformLocation(p, "motionThreshold"), 0.045f);
        glUniform1i(glGetUniformLocation(p, "historyReady"), historyReady_);
        glDrawArrays(GL_TRIANGLES, 0, 3);
        history_ = next;
        historyReady_ = true;
    }
    void present()
    {
        int drawableWidth, drawableHeight;
        SDL_GL_GetDrawableSize(window_, &drawableWidth, &drawableHeight);
        glBindFramebuffer(GL_FRAMEBUFFER, 0);
        glViewport(0, 0, drawableWidth, drawableHeight);
        glClearColor(0.025f, 0.025f, 0.025f, 1.0f); glClear(GL_COLOR_BUFFER_BIT);
        float scale = std::min(float(drawableWidth) / width_, float(drawableHeight) / height_);
        int w = int(width_ * scale), h = int(height_ * scale);
        glViewport((drawableWidth - w) / 2, (drawableHeight - h) / 2, w, h);
        glUseProgram(programs_[1]);
        texture(0, textures_[0]); texture(1, textures_[1 + history_]);
        auto p = programs_[1];
        glUniform1i(glGetUniformLocation(p, "sourceFrame"), 0);
        glUniform1i(glGetUniformLocation(p, "filteredFrame"), 1);
        glUniform1i(glGetUniformLocation(p, "enabled"), enabled);
        glUniform1i(glGetUniformLocation(p, "compare"), compare);
        glUniform1f(glGetUniformLocation(p, "dividerWidth"), 1.0f / std::max(w, 1));
        glDrawArrays(GL_TRIANGLES, 0, 3);
        SDL_GL_SwapWindow(window_);
        require(glGetError() == GL_NO_ERROR, "OpenGL rendering error");
    }
    std::vector<uint8_t> readTexture(GLuint t)
    {
        std::vector<uint8_t> pixels(size_t(width_) * height_ * 4);
        glBindFramebuffer(GL_FRAMEBUFFER, framebuffer_);
        glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, t, 0);
        if (t == textures_[0]) {
            glReadPixels(0, 0, width_, height_, GL_RGBA, GL_UNSIGNED_BYTE, pixels.data());
        } else {
            std::vector<float> precise(pixels.size());
            glReadPixels(0, 0, width_, height_, GL_RGBA, GL_FLOAT, precise.data());
            for (size_t i = 0; i < pixels.size(); ++i)
                pixels[i] = uint8_t(std::clamp(precise[i], 0.0f, 1.0f) * 255.0f + 0.5f);
        }
        require(glGetError() == GL_NO_ERROR, "Cannot read filter result");
        return pixels;
    }
    std::vector<uint8_t> filtered() { return readTexture(textures_[1 + history_]); }
    void snapshot(const std::string &path)
    {
        require(!std::filesystem::exists(path), "Snapshot file already exists");
        auto original = readTexture(textures_[0]);
        auto clean = filtered();
        std::ofstream output(path, std::ios::binary);
        require(bool(output), "Cannot write snapshot");
        output << "P6\n" << width_ * 2 << ' ' << height_ << "\n255\n";
        for (unsigned y = 0; y < height_; ++y) {
            for (auto *pixels : {&original, &clean}) {
                for (unsigned x = 0; x < width_; ++x)
                    output.write(reinterpret_cast<const char *>(pixels->data() + (size_t(y) * width_ + x) * 4), 3);
            }
        }
        require(bool(output), "Snapshot write failed");
        std::cout << "SNAPSHOT left=original right=denoised " << path << std::endl;
    }
};

static int selfTest()
{
    constexpr unsigned width = 320, height = 200;
    Renderer renderer(width, height, true);
    std::mt19937 random(234);
    std::normal_distribution<float> noise(0.0f, 0.045f);
    std::vector<uint8_t> pixels(width * height * 4);
    double inputError = 0, outputError = 0, movingError = 0;
    double outputBias = 0;
    size_t staticSamples = 0, movingSamples = 0;
    for (unsigned frame = 0; frame < 180; ++frame) {
        int left = frame < 100 ? 80 : 80 + int(frame - 100);
        int previousLeft = frame <= 100 ? 80 : left - 1;
        for (unsigned y = 0; y < height; ++y) {
            for (unsigned x = 0; x < width; ++x) {
                float truth = (int(x) >= left && int(x) < left + 70 && y >= 60 && y < 140) ? 0.75f : 0.15f;
                size_t index = (size_t(y) * width + x) * 4;
                for (int channel = 0; channel < 3; ++channel)
                    pixels[index + channel] = uint8_t(std::clamp(truth + noise(random), 0.0f, 1.0f) * 255.0f + 0.5f);
                pixels[index + 3] = 255;
            }
        }
        renderer.process(pixels.data(), width * 4);
        auto filtered = renderer.filtered();
        if (frame >= 20 && frame < 100) {
            for (unsigned y = 20; y < 50; ++y) for (unsigned x = 20; x < 60; ++x) {
                size_t i = (size_t(y) * width + x) * 4;
                for (int c = 0; c < 3; ++c) {
                    double a = pixels[i + c] / 255.0 - 0.15;
                    double b = filtered[i + c] / 255.0 - 0.15;
                    inputError += a * a; outputError += b * b; outputBias += b; ++staticSamples;
                }
            }
        }
        if (frame > 100) {
            for (unsigned y = 70; y < 130; ++y) for (int x : {previousLeft, left + 69}) {
                size_t i = (size_t(y) * width + unsigned(x)) * 4;
                double truth = x == previousLeft ? 0.15 : 0.75;
                for (int c = 0; c < 3; ++c) {
                    double b = filtered[i + c] / 255.0 - truth;
                    movingError += b * b; ++movingSamples;
                }
            }
        }
    }
    double ratio = std::sqrt(outputError / inputError);
    double bias = outputBias / staticSamples;
    double movingRmse = std::sqrt(movingError / movingSamples);
    std::cout << "SELF_TEST noise_rms_ratio=" << ratio << " mean_bias=" << bias
              << " moving_edge_rmse=" << movingRmse << std::endl;
    require(ratio < 0.85 && std::abs(bias) < 0.01 && movingRmse < 0.08,
            "Noise/motion regression check failed");
    // Exercise dark grain, a dim narrow line, and a fixed green Bayer-like cross
    // together. Measure against the clean scene, not against filter internals.
    std::normal_distribution<float> darkNoise(0.0f, 0.016f);
    for (int strength = 1; strength <= 3; ++strength) {
        renderer.strength = strength;
        renderer.resetHistory();
        double darkInput = 0, darkOutput = 0, darkBias = 0, lineContrast = 0;
        double greenExcess = 0, darkMovingError = 0;
        size_t darkSamples = 0, lineSamples = 0, pointSamples = 0, darkMovingSamples = 0;
        for (unsigned frame = 0; frame < 110; ++frame) {
            int left = frame < 60 ? 160 : 160 + int(frame - 60);
            for (unsigned y = 0; y < height; ++y) for (unsigned x = 0; x < width; ++x) {
                float truth = 0.04f;
                if (x >= 90 && x <= 92 && y >= 10 && y < 190) truth = 0.065f;
                if (int(x) >= left && int(x) < left + 50 && y >= 60 && y < 140) truth = 0.15f;
                size_t i = (size_t(y) * width + x) * 4;
                for (int c = 0; c < 3; ++c)
                    pixels[i + c] = uint8_t(std::clamp(truth + darkNoise(random), 0.0f, 1.0f) * 255.0f + 0.5f);
                pixels[i + 3] = 255;
            }
            for (auto point : {std::pair<int, int>{42, 35}, {41, 35}, {43, 35}, {42, 34}, {42, 36}}) {
                size_t i = (size_t(point.second) * width + point.first) * 4;
                pixels[i + 1] = point.first == 42 && point.second == 35 ? 195 : 100;
            }
            renderer.process(pixels.data(), width * 4);
            auto clean = renderer.filtered();
            if (frame >= 20 && frame < 60) {
                for (unsigned y = 20; y < 50; ++y) for (unsigned x = 15; x < 30; ++x) {
                    size_t i = (size_t(y) * width + x) * 4;
                    for (int c = 0; c < 3; ++c) {
                        double a = pixels[i + c] / 255.0 - 0.04;
                        double b = clean[i + c] / 255.0 - 0.04;
                        darkInput += a * a; darkOutput += b * b; darkBias += b; ++darkSamples;
                    }
                }
                for (unsigned y = 30; y < 170; ++y) for (unsigned x = 90; x <= 92; ++x) {
                    size_t i = (size_t(y) * width + x) * 4;
                    for (int c = 0; c < 3; ++c) {
                        lineContrast += clean[i + c] / 255.0 - 0.04; ++lineSamples;
                    }
                }
                for (int y = 34; y <= 36; ++y) for (int x = 41; x <= 43; ++x) {
                    size_t i = (size_t(y) * width + x) * 4;
                    greenExcess += clean[i + 1] / 255.0 - (clean[i] + clean[i + 2]) / 510.0;
                    ++pointSamples;
                }
            }
            if (frame > 60) {
                for (unsigned y = 70; y < 130; ++y) for (int x : {left - 1, left + 49}) {
                    size_t i = (size_t(y) * width + unsigned(x)) * 4;
                    double truth = x == left - 1 ? 0.04 : 0.15;
                    for (int c = 0; c < 3; ++c) {
                        double b = clean[i + c] / 255.0 - truth;
                        darkMovingError += b * b; ++darkMovingSamples;
                    }
                }
            }
        }
        double darkRatio = std::sqrt(darkOutput / darkInput);
        double meanBias = darkBias / darkSamples;
        double retainedContrast = lineContrast / lineSamples / 0.025;
        double remainingGreen = greenExcess / pointSamples;
        double darkEdgeRmse = std::sqrt(darkMovingError / darkMovingSamples);
        std::cout << "SHADOW_TEST strength=" << strength << " noise_rms_ratio=" << darkRatio
                  << " mean_bias=" << meanBias << " dim_line_contrast=" << retainedContrast
                  << " green_excess=" << remainingGreen << " moving_edge_rmse=" << darkEdgeRmse << std::endl;
        require(darkRatio < 0.60 && std::abs(meanBias) < 0.005 && retainedContrast > 0.70 &&
                std::abs(remainingGreen) < 0.02 && darkEdgeRmse < 0.04,
                "Shadow/detail/outlier regression check failed");
    }
    return 0;
}

int main(int argc, char **argv)
{
    try {
        unsigned frameLimit = 0, wantedWidth = 1920, wantedHeight = 1080;
        std::string snapshot, cameraId;
        bool comparison = false, listCameras = false;
        for (int i = 1; i < argc; ++i) {
            std::string option(argv[i]);
            if (option == "--self-test") return selfTest();
            if (option == "--compare") comparison = true;
            else if (option == "--list-cameras") listCameras = true;
            else if (option == "--help") {
                std::cout << "IMX519 preview: --camera=ID --list-cameras --compare --width=N --height=N\n"
                             "  --frames=N --snapshot=FILE.ppm --self-test\n"
                             "Keys: N filter, C compare, 1/2/3 strength, F fullscreen, Esc/Q quit\n";
                return 0;
            }
            else if (option.rfind("--camera=", 0) == 0) {
                cameraId = option.substr(9);
                require(!cameraId.empty(), "--camera requires an exact libcamera ID");
            }
            else if (option.rfind("--frames=", 0) == 0) frameLimit = std::stoul(option.substr(9));
            else if (option.rfind("--snapshot=", 0) == 0) snapshot = option.substr(11);
            else if (option.rfind("--width=", 0) == 0) wantedWidth = std::stoul(option.substr(8));
            else if (option.rfind("--height=", 0) == 0) wantedHeight = std::stoul(option.substr(9));
            else throw std::runtime_error("Unknown option: " + option);
        }
        if (listCameras) {
            CameraManager manager;
            require(manager.start() == 0, "Cannot start libcamera");
            for (const auto &camera : manager.cameras())
                if (camera->id().find("imx519") != std::string::npos)
                    std::cout << camera->id() << '\n';
            manager.stop();
            return 0;
        }
        require(wantedWidth > 0 && wantedHeight > 0, "Width and height must be positive");
        require(snapshot.empty() || frameLimit > 0, "A snapshot requires --frames=N");
        std::signal(SIGINT, signalHandler); std::signal(SIGTERM, signalHandler);
        Capture capture;
        capture.start(wantedWidth, wantedHeight, cameraId);
        Renderer renderer(capture.width, capture.height);
        renderer.compare = comparison;
        // Compile/prime the render passes before the sensor starts delivering frames.
        std::vector<uint8_t> warmup(size_t(capture.stride) * capture.height, 0);
        for (int i = 0; i < 2; ++i) {
            renderer.process(warmup.data(), capture.stride);
            renderer.present();
        }
        glFinish();
        renderer.resetHistory();
        capture.begin();
        unsigned displayed = 0, reportFrames = 0;
        uint64_t firstTimestamp = 0, lastTimestamp = 0;
        auto started = Clock::now(), lastReport = started, lastFrame = started;
        while (!interrupted && renderer.events() && (!frameLimit || displayed < frameLimit)) {
            Request *request = capture.next();
            if (!request) {
                require(Clock::now() - lastFrame < std::chrono::seconds(10), "Camera stopped producing frames");
                continue;
            }
            FrameBuffer *buffer = capture.buffer(request);
            if (buffer->metadata().status != FrameMetadata::FrameSuccess) {
                ++capture.errors; capture.recycle(request); continue;
            }
            if (!displayed) firstTimestamp = buffer->metadata().timestamp;
            lastTimestamp = buffer->metadata().timestamp;
            const uint8_t *data = capture.beginRead(request);
            renderer.process(data, capture.stride);
            capture.endRead(request);
            capture.recycle(request);
            renderer.present();
            ++displayed; lastFrame = Clock::now();
            double interval = std::chrono::duration<double>(lastFrame - lastReport).count();
            if (interval >= 3.0) {
                double fps = (displayed - reportFrames) / interval;
                renderer.updateTitle(fps);
                std::cout << "PERF fps=" << fps << " frames=" << displayed << " dropped="
                          << capture.dropped << " errors=" << capture.errors << std::endl;
                reportFrames = displayed; lastReport = lastFrame;
            }
        }
        if (!snapshot.empty() && displayed) renderer.snapshot(snapshot);
        capture.stop();
        double seconds = std::chrono::duration<double>(Clock::now() - started).count();
        double fps = displayed > 1 && lastTimestamp > firstTimestamp ?
                     (displayed - 1) * 1e9 / double(lastTimestamp - firstTimestamp) : 0;
        std::cout << "RESULT frames=" << displayed << " output_fps=" << fps
                  << " seconds=" << seconds << " dropped=" << capture.dropped
                  << " errors=" << capture.errors << std::endl;
        return frameLimit && displayed != frameLimit ? 2 : 0;
    } catch (const std::exception &error) {
        std::cerr << "ERROR " << error.what() << std::endl;
        return 1;
    }
}
