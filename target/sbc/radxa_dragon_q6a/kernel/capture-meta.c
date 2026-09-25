// SPDX-License-Identifier: GPL-2.0
// Capture small V4L2_META_CAPTURE samples, retaining sequence and timestamp.
#include <errno.h>
#include <fcntl.h>
#include <linux/videodev2.h>
#include <poll.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <unistd.h>

#define BUFFER_COUNT 4
#ifndef V4L2_META_FMT_GENERIC_8
#define V4L2_META_FMT_GENERIC_8 v4l2_fourcc('M', 'E', 'T', '8')
#endif

struct mapped_buffer {
	void *data;
	size_t length;
};

static int checked_ioctl(int fd, unsigned long request, void *arg,
			 const char *name)
{
	int ret;
	do {
		ret = ioctl(fd, request, arg);
	} while (ret < 0 && errno == EINTR);
	if (ret < 0)
		perror(name);
	return ret;
}

int main(int argc, char **argv)
{
	struct mapped_buffer buffers[BUFFER_COUNT] = { 0 };
	struct v4l2_requestbuffers req = {
		.count = BUFFER_COUNT,
		.type = V4L2_BUF_TYPE_META_CAPTURE,
		.memory = V4L2_MEMORY_MMAP,
	};
	struct v4l2_format fmt = { .type = V4L2_BUF_TYPE_META_CAPTURE };
	enum v4l2_buf_type type = V4L2_BUF_TYPE_META_CAPTURE;
	FILE *manifest;
	char path[512];
	unsigned int count;
	int fd, ret = 1;

	if (argc != 4 || sscanf(argv[3], "%u", &count) != 1 || count > 1000) {
		fprintf(stderr, "Usage: %s VIDEO_NODE OUTPUT_DIR COUNT(0=queue probe, 1..1000=frames)\n", argv[0]);
		return 2;
	}
	fd = open(argv[1], O_RDWR | O_CLOEXEC);
	if (fd < 0) {
		perror(argv[1]);
		return 1;
	}
	if (checked_ioctl(fd, VIDIOC_G_FMT, &fmt, "VIDIOC_G_FMT") ||
	    fmt.fmt.meta.dataformat != V4L2_META_FMT_GENERIC_8) {
		fprintf(stderr, "Metadata format MET8 must be configured first\n");
		goto close_fd;
	}
	printf("MET8 buffer size: %u\n", fmt.fmt.meta.buffersize);
	if (checked_ioctl(fd, VIDIOC_REQBUFS, &req, "VIDIOC_REQBUFS") ||
	    req.count < 2 || req.count > BUFFER_COUNT)
		goto close_fd;
	fprintf(stderr, "Allocated %u metadata buffers\n", req.count);
	for (unsigned int i = 0; i < req.count; ++i) {
		struct v4l2_buffer buf = {
			.type = type,
			.memory = V4L2_MEMORY_MMAP,
			.index = i,
		};
		if (checked_ioctl(fd, VIDIOC_QUERYBUF, &buf, "VIDIOC_QUERYBUF"))
			goto cleanup;
		fprintf(stderr, "QUERYBUF %u: %u bytes\n", i, buf.length);
		if (!count)
			continue;
		buffers[i].length = buf.length;
		buffers[i].data = mmap(NULL, buf.length, PROT_READ | PROT_WRITE,
				       MAP_SHARED, fd, buf.m.offset);
		if (buffers[i].data == MAP_FAILED) {
			buffers[i].data = NULL;
			perror("mmap");
			goto cleanup;
		}
		if (checked_ioctl(fd, VIDIOC_QBUF, &buf, "VIDIOC_QBUF"))
			goto cleanup;
	}
	if (!count) {
		ret = 0;
		goto close_fd;
	}
	if (snprintf(path, sizeof(path), "%s/frames.csv", argv[2]) >= (int)sizeof(path))
		goto cleanup;
	manifest = fopen(path, "w");
	if (!manifest) {
		perror(path);
		goto cleanup;
	}
	fputs("frame,sequence,timestamp_sec,timestamp_usec,bytesused\n", manifest);
	if (checked_ioctl(fd, VIDIOC_STREAMON, &type, "VIDIOC_STREAMON"))
		goto close_manifest;
	for (unsigned int n = 0; n < count; ++n) {
		struct pollfd pfd = { .fd = fd, .events = POLLIN };
		struct v4l2_buffer buf = {
			.type = type,
			.memory = V4L2_MEMORY_MMAP,
		};
		FILE *sample;

		int ready = poll(&pfd, 1, 5000);
		if (ready <= 0) {
			if (ready == 0)
				fprintf(stderr, "metadata poll timed out\n");
			else
				perror("metadata poll");
			goto stop_stream;
		}
		if (checked_ioctl(fd, VIDIOC_DQBUF, &buf, "VIDIOC_DQBUF"))
			goto stop_stream;
		if (buf.index >= req.count || buf.bytesused > buffers[buf.index].length)
			goto stop_stream;
		if (snprintf(path, sizeof(path), "%s/frame-%04u.bin", argv[2], n) >= (int)sizeof(path))
			goto stop_stream;
		sample = fopen(path, "wb");
		if (!sample) {
			perror(path);
			goto stop_stream;
		}
		if (fwrite(buffers[buf.index].data, 1, buf.bytesused, sample) != buf.bytesused) {
			perror("fwrite");
			fclose(sample);
			goto stop_stream;
		}
		fclose(sample);
		fprintf(manifest, "%u,%u,%ld,%ld,%u\n", n, buf.sequence,
			(long)buf.timestamp.tv_sec, (long)buf.timestamp.tv_usec,
			buf.bytesused);
		printf("frame=%u sequence=%u bytes=%u timestamp=%ld.%06ld\n", n,
		       buf.sequence, buf.bytesused, (long)buf.timestamp.tv_sec,
		       (long)buf.timestamp.tv_usec);
		if (checked_ioctl(fd, VIDIOC_QBUF, &buf, "VIDIOC_QBUF"))
			goto stop_stream;
	}
	ret = 0;
stop_stream:
	checked_ioctl(fd, VIDIOC_STREAMOFF, &type, "VIDIOC_STREAMOFF");
close_manifest:
	fclose(manifest);
cleanup:
	for (unsigned int i = 0; i < req.count; ++i)
		if (buffers[i].data)
			munmap(buffers[i].data, buffers[i].length);
close_fd:
	close(fd);
	return ret;
}
