# বেস ইমেজ হিসেবে Python 3.9 ব্যবহার করা হচ্ছে
FROM python:3.9-slim

# এনভায়রনমেন্ট ভ্যারিয়েবল সেট করা হচ্ছে যাতে ইনস্টলের সময় কোনো প্রম্পট না আসে
ENV DEBIAN_FRONTEND=noninteractive

# প্রয়োজনীয় ডিপেন্ডেন্সি ইনস্টল করা: FFmpeg, Xvfb, Chromium, ChromeDriver
# এবং Selenium ও অন্যান্য প্রয়োজনীয় লাইব্রেরি
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    xvfb \
    chromium \
    chromium-driver \
    # যদি chromium বা ffmpeg চালাতে অন্য কোনো লাইব্রেরির প্রয়োজন হয়, এখানে যোগ করতে হবে
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Python লাইব্রেরি ইনস্টল করা
RUN pip install selenium

# অ্যাপ্লিকেশনের জন্য ওয়ার্কিং ডিরেক্টরি সেট করা
WORKDIR /app

# HLS আউটপুট ডিরেক্টরি তৈরি করা
RUN mkdir hls

# পাইথন স্ক্রিপ্ট কপি করা
COPY streamer.py .

# HTTP সার্ভারের জন্য পোর্ট এক্সপোজ করা
EXPOSE 8080

# কন্টেইনার চালু হলে যে কমান্ড রান হবে
# পাইথন স্ক্রিপ্টটি Xvfb, ব্রাউজার, FFmpeg এবং HTTP সার্ভার চালু করবে
CMD ["python", "streamer.py"]
