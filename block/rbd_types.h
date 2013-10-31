/*
 * Types and signatures for librados and librbd
 *
 * Copyright (C) 2013 Inktank Storage Inc.
 *
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public
 * License as published by the Free Software Foundation; either
 * version 2 of the License, or (at your option) any later version.
 *
 * This library is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public
 * License along with this library; if not, see <http://www.gnu.org/licenses/>.
 */

#ifndef QEMU_BLOCK_RBD_TYPES_H
#define QEMU_BLOCK_RBD_TYPES_H

/* types from librados used by the rbd block driver */

typedef void *rados_t;
typedef void *rados_ioctx_t;

typedef struct LibradosFuncs {
    int  (*rados_create)(rados_t *cluster, const char * const id);
    int  (*rados_connect)(rados_t cluster);
    void (*rados_shutdown)(rados_t cluster);
    int  (*rados_conf_read_file)(rados_t cluster, const char *path);
    int  (*rados_conf_set)(rados_t cluster, const char *option,
                           const char *value);
    int  (*rados_ioctx_create)(rados_t cluster, const char *pool_name,
                               rados_ioctx_t *ioctx);
    void (*rados_ioctx_destroy)(rados_ioctx_t io);
} LibradosFuncs;

/* types from librbd used by the rbd block driver*/

typedef void *rbd_image_t;
typedef void *rbd_completion_t;
typedef void (*rbd_callback_t)(rbd_completion_t cb, void *arg);

typedef struct {
    uint64_t id;
    uint64_t size;
    const char *name;
} rbd_snap_info_t;

#define RBD_MAX_IMAGE_NAME_SIZE 96
#define RBD_MAX_BLOCK_NAME_SIZE 24

typedef struct {
    uint64_t size;
    uint64_t obj_size;
    uint64_t num_objs;
    int order;
    char block_name_prefix[RBD_MAX_BLOCK_NAME_SIZE];
    int64_t parent_pool;
    char parent_name[RBD_MAX_IMAGE_NAME_SIZE];
} rbd_image_info_t;

typedef struct LibrbdFuncs {
    int     (*rbd_create)(rados_ioctx_t io, const char *name, uint64_t size,
                          int *order);
    int     (*rbd_open)(rados_ioctx_t io, const char *name, rbd_image_t *image,
                        const char *snap_name);
    int     (*rbd_close)(rbd_image_t image);
    int     (*rbd_resize)(rbd_image_t image, uint64_t size);
    int     (*rbd_stat)(rbd_image_t image, rbd_image_info_t *info,
                        size_t infosize);
    int     (*rbd_snap_list)(rbd_image_t image, rbd_snap_info_t *snaps,
                             int *max_snaps);
    void    (*rbd_snap_list_end)(rbd_snap_info_t *snaps);
    int     (*rbd_snap_create)(rbd_image_t image, const char *snapname);
    int     (*rbd_snap_remove)(rbd_image_t image, const char *snapname);
    int     (*rbd_snap_rollback)(rbd_image_t image, const char *snapname);
    int     (*rbd_aio_write)(rbd_image_t image, uint64_t off, size_t len,
                             const char *buf, rbd_completion_t c);
    int     (*rbd_aio_read)(rbd_image_t image, uint64_t off, size_t len,
                            char *buf, rbd_completion_t c);
    int     (*rbd_aio_discard)(rbd_image_t image, uint64_t off, uint64_t len,
                               rbd_completion_t c);
    int     (*rbd_aio_create_completion)(void *cb_arg,
                                         rbd_callback_t complete_cb,
                                         rbd_completion_t *c);
    ssize_t (*rbd_aio_get_return_value)(rbd_completion_t c);
    void    (*rbd_aio_release)(rbd_completion_t c);
    int     (*rbd_flush)(rbd_image_t image);
    int     (*rbd_aio_flush)(rbd_image_t image, rbd_completion_t c);
} LibrbdFuncs;

#endif
