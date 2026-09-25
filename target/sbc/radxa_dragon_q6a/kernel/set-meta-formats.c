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

static int get_format(const char *node, unsigned int pad,
		      struct v4l2_mbus_framefmt *format)
{
	struct v4l2_subdev_format fmt = {
		.which = V4L2_SUBDEV_FORMAT_ACTIVE,
		.pad = pad,
	};
	int fd = open(node, O_RDWR | O_CLOEXEC);
	int ret;

	if (fd < 0) {
		perror(node);
		return -1;
	}
	ret = ioctl(fd, VIDIOC_SUBDEV_G_FMT, &fmt);
	if (ret < 0)
		perror("VIDIOC_SUBDEV_G_FMT");
	else
		*format = fmt.format;
	close(fd);
	return ret;
}

static int set_format(const char *node, unsigned int pad,
		      const struct v4l2_mbus_framefmt *format)
{
	struct v4l2_subdev_format fmt = {
		.which = V4L2_SUBDEV_FORMAT_ACTIVE,
		.pad = pad,
		.format = *format,
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
	return fmt.format.code == format->code &&
	       fmt.format.width == format->width &&
	       fmt.format.height == format->height ? 0 : -1;
}

int main(int argc, char **argv)
{
	struct v4l2_mbus_framefmt image;
	struct v4l2_mbus_framefmt metadata = {
		.height = 1,
		.code = MEDIA_BUS_FMT_SENSOR_DATA,
		.field = V4L2_FIELD_NONE,
	};
	struct v4l2_mbus_framefmt phase = {
		.height = 1,
		.code = MEDIA_BUS_FMT_SENSOR_DATA,
		.field = V4L2_FIELD_NONE,
	};

	if (argc != 5 && argc != 6) {
		fprintf(stderr, "Usage: %s SENSOR_SUBDEV CSIPHY_SUBDEV CSID_SUBDEV VFE_RDI1_SUBDEV [VFE_RDI2_SUBDEV]\n", argv[0]);
		return 2;
	}
	if (get_format(argv[1], 0, &image))
		return 1;
	if (image.code != MEDIA_BUS_FMT_SRGGB10_1X10 || image.width % 4) {
		fprintf(stderr, "Expected IMX519 packed RAW10 width, got code 0x%x width %u\n",
			image.code, image.width);
		return 1;
	}
	/* Two DT 0x12 rows and one separate DT 0x36 row, each width * 10 / 8. */
	phase.width = image.width * 5 / 4;
	metadata.width = 2 * phase.width;
	if (set_format(argv[2], 0, &image) ||
	    set_format(argv[3], 0, &image) ||
	    set_format(argv[3], 2, &metadata) ||
	    set_format(argv[4], 0, &metadata))
		return 1;
	if (argc == 6 && (set_format(argv[3], 3, &phase) ||
			  set_format(argv[5], 0, &phase)))
		return 1;
	return 0;
}
