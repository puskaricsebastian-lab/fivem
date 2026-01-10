const defaultConfig = {
  serverName: 'Hayat City',
  slogan: 'Dein Leben. Deine Story.',
  welcomeText: 'Willkommen in Hayat City — wir freuen uns, dass du da bist.',
  discord: 'discord.gg/hayatcity',
  themeColor: '#7c3aed',
  secondaryColor: '#8b5cf6',
  accentGlow: 'rgba(124, 58, 237, 0.6)',
  background: {
    useYoutube: true,
    youtubeUrl: 'https://www.youtube.com/watch?v=ScMzIvxBSi4',
    localVideoPath: 'assets/video/background.mp4',
    blur: 6,
    overlayOpacity: 0.45
  },
  music: {
    useYoutube: true,
    youtubeUrl: 'https://www.youtube.com/watch?v=jfKfPfyJRdk',
    trackName: 'Lofi Hip Hop Radio',
    localAudioPath: 'assets/music/loading.mp3',
    defaultVolume: 0.25
  },
  showLogo: true,
  logoFileName: 'logo-main.png',
  showBanner: true,
  bannerFileName: 'banner.png',
  showSnow: false,
  loadingTips: [
    'Halte deine Papiere bereit — RP beginnt sofort.',
    'Drücke F1 für dein Inventar (falls vorhanden).',
    'Stimme dich mit anderen ab, bevor du loslegst.',
    'Respektiere andere Spieler und habe Spaß.'
  ]
};

let config = { ...defaultConfig };
let youtubeReady = false;
let youtubeQueue = [];
let backgroundPlayer = null;
let musicPlayer = null;
let localAudio = null;
let progressValue = 0;
let tipIndex = 0;
let autoProgressInterval = null;

const elements = {
  backgroundMedia: document.getElementById('background-media'),
  backgroundOverlay: document.getElementById('background-overlay'),
  serverName: document.getElementById('server-name'),
  serverSlogan: document.getElementById('server-slogan'),
  discord: document.getElementById('discord'),
  logo: document.getElementById('logo-image'),
  banner: document.getElementById('banner-image'),
  progressFill: document.getElementById('progress-fill'),
  progressValue: document.getElementById('progress-value'),
  loadingTip: document.getElementById('loading-tip'),
  particles: document.getElementById('particles'),
  trackTitle: document.getElementById('track-title'),
  trackTime: document.getElementById('track-time'),
  trackSeek: document.getElementById('track-seek')
};

const controls = {
  playPause: document.getElementById('play-pause'),
  volumeDown: document.getElementById('volume-down'),
  volumeUp: document.getElementById('volume-up')
};

const applyConfig = (newConfig) => {
  config = { ...config, ...newConfig };

  document.documentElement.style.setProperty('--theme-color', config.themeColor);
  document.documentElement.style.setProperty('--secondary-color', config.secondaryColor);
  document.documentElement.style.setProperty('--accent-glow', config.accentGlow);
  document.documentElement.style.setProperty('--overlay-opacity', config.background.overlayOpacity);
  document.documentElement.style.setProperty('--background-blur', `${config.background.blur}px`);

  elements.serverName.textContent = config.serverName;
  elements.serverSlogan.textContent = config.slogan;
  elements.discord.textContent = config.discord || '';

  elements.discord.style.display = config.discord ? 'inline-flex' : 'none';

  if (config.showLogo) {
    elements.logo.src = `assets/images/${config.logoFileName}`;
    elements.logo.style.display = 'block';
  } else {
    elements.logo.style.display = 'none';
  }

  if (config.showBanner) {
    elements.banner.src = `assets/images/${config.bannerFileName}`;
    elements.banner.style.display = 'block';
  } else {
    elements.banner.style.display = 'none';
  }

  setupBackground();
  setupMusic();
  updateTrackTitle();
  setupTips();
  setupParticles();
};

const setupBackground = () => {
  elements.backgroundMedia.innerHTML = '';

  if (config.background.useYoutube) {
    const videoId = extractYoutubeId(config.background.youtubeUrl);
    if (!videoId) {
      setupLocalVideo();
      return;
    }

    loadYoutubeApi(() => {
      const container = document.createElement('div');
      container.id = 'yt-background';
      elements.backgroundMedia.appendChild(container);

      backgroundPlayer = new YT.Player(container, {
        videoId,
        playerVars: {
          autoplay: 1,
          controls: 0,
          disablekb: 1,
          fs: 0,
          loop: 1,
          modestbranding: 1,
          playsinline: 1,
          rel: 0,
          playlist: videoId,
          mute: 1
        },
        events: {
          onReady: (event) => {
            event.target.mute();
            event.target.playVideo();
          }
        }
      });
    });
  } else {
    setupLocalVideo();
  }
};

const setupLocalVideo = () => {
  const video = document.createElement('video');
  video.src = config.background.localVideoPath;
  video.preload = 'auto';
  video.autoplay = true;
  video.loop = true;
  video.muted = true;
  video.playsInline = true;
  video.load();
  elements.backgroundMedia.appendChild(video);
};

const setupMusic = () => {
  localAudio = null;
  musicPlayer = null;

  if (config.music.useYoutube) {
    const videoId = extractYoutubeId(config.music.youtubeUrl);
    if (!videoId) {
      setupLocalAudio();
      return;
    }

    loadYoutubeApi(() => {
      const container = document.createElement('div');
      container.id = 'yt-music';
      container.style.position = 'absolute';
      container.style.left = '-9999px';
      container.style.top = '-9999px';
      document.body.appendChild(container);

      musicPlayer = new YT.Player(container, {
        videoId,
        playerVars: {
          autoplay: 1,
          controls: 0,
          loop: 1,
          modestbranding: 1,
          playsinline: 1,
          rel: 0,
          playlist: videoId
        },
        events: {
          onReady: (event) => {
            event.target.setVolume(config.music.defaultVolume * 100);
            event.target.playVideo();
            event.target.unMute();
            startTrackTimer();
          }
        }
      });
    });
  } else {
    setupLocalAudio();
  }
};

const setupLocalAudio = () => {
  localAudio = document.createElement('audio');
  localAudio.src = config.music.localAudioPath;
  localAudio.preload = 'auto';
  localAudio.loop = true;
  localAudio.volume = config.music.defaultVolume;
  localAudio.autoplay = true;
  document.body.appendChild(localAudio);
  localAudio.muted = false;
  localAudio.load();
  localAudio.play().catch(() => {});
  localAudio.addEventListener('loadedmetadata', () => {
    updateTrackTime(localAudio.currentTime, localAudio.duration);
  });
  localAudio.addEventListener('timeupdate', () => {
    updateTrackTime(localAudio.currentTime, localAudio.duration);
  });
};

const startTrackTimer = () => {
  setInterval(() => {
    if (!musicPlayer) {
      return;
    }
    const current = musicPlayer.getCurrentTime();
    const duration = musicPlayer.getDuration();
    updateTrackTime(current, duration);
  }, 500);
};

const updateTrackTitle = () => {
  const title = config.music.trackName || (config.music.useYoutube ? 'YouTube Audio' : 'Lokale Musik');
  elements.trackTitle.textContent = title;
};

const updateTrackTime = (current, duration) => {
  if (!duration || Number.isNaN(duration)) {
    elements.trackTime.textContent = '0:00 / 0:00';
    elements.trackSeek.value = 0;
    return;
  }

  const currentText = formatTime(current);
  const durationText = formatTime(duration);
  elements.trackTime.textContent = `${currentText} / ${durationText}`;
  elements.trackSeek.value = Math.min(100, Math.max(0, (current / duration) * 100));
};

const formatTime = (time) => {
  const minutes = Math.floor(time / 60);
  const seconds = Math.floor(time % 60);
  return `${minutes}:${seconds.toString().padStart(2, '0')}`;
};

const setupTips = () => {
  if (!config.loadingTips || config.loadingTips.length === 0) {
    elements.loadingTip.textContent = '';
    return;
  }

  elements.loadingTip.textContent = config.loadingTips[0];
  tipIndex = 0;

  setInterval(() => {
    tipIndex = (tipIndex + 1) % config.loadingTips.length;
    elements.loadingTip.textContent = config.loadingTips[tipIndex];
  }, 6000);
};

const setupParticles = () => {
  elements.particles.innerHTML = '';
  if (!config.showSnow) {
    return;
  }

  for (let i = 0; i < 30; i += 1) {
    const particle = document.createElement('div');
    particle.className = 'particle';
    particle.style.left = `${Math.random() * 100}%`;
    particle.style.animationDelay = `${Math.random() * 8}s`;
    particle.style.animationDuration = `${6 + Math.random() * 6}s`;
    particle.style.opacity = `${0.4 + Math.random() * 0.6}`;
    particle.style.transform = `scale(${0.6 + Math.random() * 0.8})`;
    elements.particles.appendChild(particle);
  }
};

const updateProgress = (value) => {
  progressValue = Math.min(100, Math.max(0, value));
  elements.progressFill.style.width = `${progressValue}%`;
  elements.progressValue.textContent = `${progressValue}%`;
};

const startAutoProgress = () => {
  if (autoProgressInterval) {
    return;
  }

  autoProgressInterval = setInterval(() => {
    if (progressValue >= 95) {
      return;
    }

    const increment = 0.6 + Math.random() * 1.2;
    updateProgress(progressValue + increment);
  }, 220);
};

const finishProgress = () => {
  updateProgress(100);
  if (autoProgressInterval) {
    clearInterval(autoProgressInterval);
    autoProgressInterval = null;
  }
};

const extractYoutubeId = (url) => {
  if (!url) {
    return null;
  }

  const match = url.match(/(?:v=|be\/|embed\/)([\w-]{11})/);
  return match ? match[1] : null;
};

const loadYoutubeApi = (callback) => {
  if (youtubeReady) {
    callback();
    return;
  }

  youtubeQueue.push(callback);

  if (document.getElementById('youtube-api')) {
    return;
  }

  const tag = document.createElement('script');
  tag.src = 'https://www.youtube.com/iframe_api';
  tag.id = 'youtube-api';
  document.body.appendChild(tag);
};

window.onYouTubeIframeAPIReady = () => {
  youtubeReady = true;
  youtubeQueue.forEach((cb) => cb());
  youtubeQueue = [];
};

controls.playPause.addEventListener('click', () => {
  if (musicPlayer) {
    const state = musicPlayer.getPlayerState();
    if (state === YT.PlayerState.PLAYING) {
      musicPlayer.pauseVideo();
    } else {
      musicPlayer.playVideo();
    }
    return;
  }

  if (localAudio) {
    if (localAudio.paused) {
      localAudio.play().catch(() => {});
    } else {
      localAudio.pause();
    }
  }
});

controls.volumeUp.addEventListener('click', () => {
  if (musicPlayer) {
    const volume = Math.min(100, musicPlayer.getVolume() + 10);
    musicPlayer.setVolume(volume);
    return;
  }

  if (localAudio) {
    localAudio.volume = Math.min(1, localAudio.volume + 0.1);
  }
});

controls.volumeDown.addEventListener('click', () => {
  if (musicPlayer) {
    const volume = Math.max(0, musicPlayer.getVolume() - 10);
    musicPlayer.setVolume(volume);
    return;
  }

  if (localAudio) {
    localAudio.volume = Math.max(0, localAudio.volume - 0.1);
  }
});

elements.trackSeek.addEventListener('input', (event) => {
  const percent = Number(event.target.value) / 100;
  if (musicPlayer) {
    const duration = musicPlayer.getDuration();
    if (duration) {
      musicPlayer.seekTo(duration * percent, true);
    }
    return;
  }

  if (localAudio && localAudio.duration) {
    localAudio.currentTime = localAudio.duration * percent;
  }
});

window.addEventListener('message', (event) => {
  const data = event.data;
  if (!data || !data.type) {
    return;
  }

  if (data.type === 'config') {
    applyConfig(data.payload);
  }

  if (data.type === 'progress') {
    updateProgress(data.value);
  }

  if (data.type === 'ready') {
    finishProgress();
  }
});

document.addEventListener('DOMContentLoaded', () => {
  applyConfig(config);
  updateProgress(0);
  startAutoProgress();
});
