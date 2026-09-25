// SPDX-License-Identifier: GPL-2.0
// Capture RAW V4L2 buffer timing without copying large images to disk.
#include <errno.h>
#include <fcntl.h>
#include <linux/videodev2.h>
#include <poll.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>

#define BUFFER_COUNT 4

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
	struct v4l2_requestbuffers req = {
		.count = BUFFER_COUNT,
		.type = V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE,
		.memory = V4L2_MEMORY_MMAP,
	};
	enum v4l2_buf_type type = req.type;
	unsigned int count;
	FILE *manifest;
	int fd, ret = 1;

	if (argc != 4 || sscanf(argv[3], "%u", &count) != 1 ||
	    count < 2 || count > 100000) {
		fprintf(stderr, "Usage: %s VIDEO_NODE FRAMES_CSV COUNT\n", argv[0]);
		return 2;
	}
	fd = open(argv[1], O_RDWR | O_CLOEXEC);
	if (fd < 0) {
		perror(argv[1]);
		return 1;
	}
	if (checked_ioctl(fd, VIDIOC_REQBUFS, &req, "VIDIOC_REQBUFS") ||
	    req.count < 2 || req.count > BUFFER_COUNT)
		goto close_fd;
	for (unsigned int i = 0; i < req.count; ++i) {
		struct v4l2_plane plane = { 0 };
		struct v4l2_buffer buf = {
			.type = type,
			.memory = V4L2_MEMORY_MMAP,
			.index = i,
			.length = 1,
			.m.planes = &plane,
		};
		if (checked_ioctl(fd, VIDIOC_QUERYBUF, &buf, "VIDIOC_QUERYBUF") ||
		    checked_ioctl(fd, VIDIOC_QBUF, &buf, "VIDIOC_QBUF"))
			goto close_fd;
	}
	manifest = fopen(argv[2], "w");
	if (!manifest) {
		perror(argv[2]);
		goto close_fd;
	}
	fputs("frame,sequence,timestamp_sec,timestamp_usec,bytesused\n", manifest);
	if (checked_ioctl(fd, VIDIOC_STREAMON, &type, "VIDIOC_STREAMON"))
		goto close_manifest;
	for (unsigned int n = 0; n < count; ++n) {
		struct pollfd pfd = { .fd = fd, .events = POLLIN };
		struct v4l2_plane plane = { 0 };
		struct v4l2_buffer buf = {
			.type = type,
			.memory = V4L2_MEMORY_MMAP,
			.length = 1,
			.m.planes = &plane,
		};
		int ready = poll(&pfd, 1, 5000);
		if (ready <= 0) {
			if (ready == 0)
				fprintf(stderr, "RAW poll timed out\n");
			else
				perror("RAW poll");
			goto stop_stream;
		}
		if (checked_ioctl(fd, VIDIOC_DQBUF, &buf, "VIDIOC_DQBUF"))
			goto stop_stream;
		if (buf.index >= req.count || buf.length != 1)
			goto stop_stream;
		fprintf(manifest, "%u,%u,%ld,%ld,%u\n", n, buf.sequence,
			(long)buf.timestamp.tv_sec, (long)buf.timestamp.tv_usec,
			plane.bytesused);
		if (checked_ioctl(fd, VIDIOC_QBUF, &buf, "VIDIOC_QBUF"))
			goto stop_stream;
	}
	ret = 0;
stop_stream:
	checked_ioctl(fd, VIDIOC_STREAMOFF, &type, "VIDIOC_STREAMOFF");
close_manifest:
	fclose(manifest);
close_fd:
	close(fd);
	return ret;
}
