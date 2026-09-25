// SPDX-License-Identifier: GPL-2.0
// Set IMX519 embedded-data media bus format where this media-ctl lacks 0x7002.
#include <errno.h>
#include <fcntl.h>
#include <linux/media-bus-format.h>
#include <linux/v4l2-subdev.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/ioctl.h>
#include <unistd.h>

static int set_format(const char *node, unsigned int pad)
{
	struct v4l2_subdev_format fmt = {
		.which = V4L2_SUBDEV_FORMAT_ACTIVE,
		.pad = pad,
		.format = {
			.width = 17460,
			.height = 1,
			.code = MEDIA_BUS_FMT_SENSOR_DATA,
			.field = V4L2_FIELD_NONE,
		},
	};
	int fd = open(node, O_RDWR | O_CLOEXEC);
	int ret;

	if (fd < 0) {
		perror(node);
		return -1;
	}
	ret = ioctl(fd, VIDIOC_SUBDEV_S_FMT, &fmt);
	if (ret < 0) {
		perror("VIDIOC_SUBDEV_S_FMT");
		close(fd);
		return -1;
	}
	printf("%s pad%u: code=0x%04x width=%u height=%u\n", node, pad,
	       fmt.format.code, fmt.format.width, fmt.format.height);
	close(fd);
	return fmt.format.code == MEDIA_BUS_FMT_SENSOR_DATA &&
	       fmt.format.width == 17460 && fmt.format.height == 1 ? 0 : -1;
}

int main(int argc, char **argv)
{
	if (argc != 3) {
		fprintf(stderr, "Usage: %s CSID_SUBDEV VFE_RDI1_SUBDEV\n", argv[0]);
		return 2;
	}
	if (set_format(argv[1], 2) || set_format(argv[2], 0))
		return 1;
	return 0;
}
