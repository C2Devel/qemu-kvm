/*
 * Helpers for getting linearized buffers from iov / filling buffers into iovs
 *
 * Copyright (C) 2010 Red Hat, Inc.
 *
 * Author(s):
 *  Amit Shah <amit.shah@redhat.com>
 *
 * This work is licensed under the terms of the GNU GPL, version 2.  See
 * the COPYING file in the top-level directory.
 */

#include "qemu-common.h"

size_t iov_from_buf(struct iovec *iov, unsigned int iovcnt,
                    const void *buf, size_t size);
size_t iov_to_buf(const struct iovec *iov, const unsigned int iovcnt,
                  void *buf, size_t offset, size_t size);
size_t iov_size(const struct iovec *iov, const unsigned int iovcnt);

/*
 * Remove a given number of bytes from the front or back of a vector.
 * This may update iov and/or iov_cnt to exclude iovec elements that are
 * no longer required.
 *
 * The number of bytes actually discarded is returned.  This number may be
 * smaller than requested if the vector is too small.
 */
size_t iov_discard_front(struct iovec **iov, unsigned int *iov_cnt,
                         size_t bytes);
size_t iov_discard_back(struct iovec *iov, unsigned int *iov_cnt,
                        size_t bytes);
