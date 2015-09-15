#ifndef QDEV_CORE_H
#define QDEV_CORE_H

#include "qemu-queue.h"
#include "qemu-option.h"
#include "qom/object.h"
#include "hw/irq.h"
#include "error.h"
#include "hw/qdev.h"
#define TYPE_DEVICE "device"
#define DEVICE(obj) OBJECT_CHECK(DeviceState, (obj), TYPE_DEVICE)
#define DEVICE_CLASS(klass) OBJECT_CLASS_CHECK(DeviceClass, (klass), TYPE_DEVICE)
#define DEVICE_GET_CLASS(obj) OBJECT_GET_CLASS(DeviceClass, (obj), TYPE_DEVICE)

typedef void (*DeviceRealize)(DeviceState *dev, Error **errp);
typedef void (*DeviceUnrealize)(DeviceState *dev, Error **errp);

struct VMStateDescription;

/**
 * DeviceClass:
 * @props: Properties accessing state fields.
 * @realize: Callback function invoked when the #DeviceState:realized
 * property is changed to %true. The default invokes @init if not %NULL.
 * @unrealize: Callback function invoked when the #DeviceState:realized
 * property is changed to %false.
 * @init: Callback function invoked when the #DeviceState::realized property
 * is changed to %true. Deprecated, new types inheriting directly from
 * TYPE_DEVICE should use @realize instead, new leaf types should consult
 * their respective parent type.
 *
 * # Realization #
 * Devices are constructed in two stages,
 * 1) object instantiation via object_initialize() and
 * 2) device realization via #DeviceState:realized property.
 * The former may not fail (it might assert or exit), the latter may return
 * error information to the caller and must be re-entrant.
 * Trivial field initializations should go into #TypeInfo.instance_init.
 * Operations depending on @props static properties should go into @realize.
 * After successful realization, setting static properties will fail.
 *
 * As an interim step, the #DeviceState:realized property is set by deprecated
 * functions qdev_init() and qdev_init_nofail().
 * In the future, devices will propagate this state change to their children
 * and along busses they expose.
 * The point in time will be deferred to machine creation, so that values
 * set in @realize will not be introspectable beforehand. Therefore devices
 * must not create children during @realize; they should initialize them via
 * object_initialize() in their own #TypeInfo.instance_init and forward the
 * realization events appropriately.
 *
 * The @init callback is considered private to a particular bus implementation
 * (immediate abstract child types of TYPE_DEVICE). Derived leaf types set an
 * "init" callback on their parent class instead.
 *
 * Any type may override the @realize and/or @unrealize callbacks but needs
 * to call the parent type's implementation if keeping their functionality
 * is desired. Refer to QOM documentation for further discussion and examples.
 *
 * <note>
 *   <para>
 * If a type derived directly from TYPE_DEVICE implements @realize, it does
 * not need to implement @init and therefore does not need to store and call
 * #DeviceClass' default @realize callback.
 * For other types consult the documentation and implementation of the
 * respective parent types.
 *   </para>
 * </note>
 */
typedef struct DeviceClass {
    /*< private >*/
    ObjectClass parent_class;
    /*< public >*/

    const char *fw_name;
    const char *desc;
    Property *props;
    int no_user;

    /* callbacks */
    void (*reset)(DeviceState *dev);
    DeviceRealize realize;
    DeviceUnrealize unrealize;

    /* device state */
    const struct VMStateDescription *vmsd;

    /* Private to qdev / bus.  */
    qdev_initfn init; /* TODO remove, once users are converted to realize */
    qdev_event unplug;
    qdev_event exit; /* TODO remove, once users are converted to unrealize */
    const char *bus_type;
} DeviceClass;

/**
 * DeviceState:
 * @realized: Indicates whether the device has been fully constructed.
 *
 * This structure should not be accessed directly.  We declare it here
 * so that it can be embedded in individual device state structures.
 */

#define TYPE_BUS "bus"
#define BUS(obj) OBJECT_CHECK(BusState, (obj), TYPE_BUS)
#define BUS_CLASS(klass) OBJECT_CLASS_CHECK(BusClass, (klass), TYPE_BUS)
#define BUS_GET_CLASS(obj) OBJECT_GET_CLASS(BusClass, (obj), TYPE_BUS)

struct BusClass {
    ObjectClass parent_class;

    /* FIXME first arg should be BusState */
    void (*print_dev)(Monitor *mon, DeviceState *dev, int indent);
    char *(*get_dev_path)(DeviceState *dev);
    /*
     * This callback is used to create Open Firmware device path in accordance
     * with OF spec http://forthworks.com/standards/of1275.pdf. Individual bus
     * bindings can be found at http://playground.sun.com/1275/bindings/.
     */
    char *(*get_fw_dev_path)(DeviceState *dev);
    int (*reset)(BusState *bus);
    /* maximum devices allowed on the bus, 0: no limit. */
    int max_dev;
};

typedef struct BusChild {
    DeviceState *child;
    int index;
    QTAILQ_ENTRY(BusChild) sibling;
} BusChild;

DeviceState *qdev_try_create(BusState *bus, const char *name);
void qdev_set_legacy_instance_id(DeviceState *dev, int alias_id,
                                 int required_for_version);


DeviceState *qdev_find_recursive(BusState *bus, const char *id);


/**
 * @qbus_reset_all:
 * @bus: Bus to be reset.
 *
 * Reset @bus and perform a bus-level ("hard") reset of all devices connected
 * to it, including recursive processing of all buses below @bus itself.  A
 * hard reset means that qbus_reset_all will reset all state of the device.
 * For PCI devices, for example, this will include the base address registers
 * or configuration space.
 */
void qbus_reset_all(BusState *bus);
void qbus_reset_all_fn(void *opaque);

/* This should go away once we get rid of the NULL bus hack */
BusState *sysbus_get_default(void);


/**
 * @qdev_machine_init
 *
 * Initialize platform devices before machine init.  This is a hack until full
 * support for composition is added.
 */
void qdev_machine_init(void);

/**
 * @device_reset
 *
 * Reset a single device (by calling the reset method).
 */
void device_reset(DeviceState *dev);

const struct VMStateDescription *qdev_get_vmsd(DeviceState *dev);


Object *qdev_get_machine(void);

/* FIXME: make this a link<> */
void qdev_set_parent_bus(DeviceState *dev, BusState *bus);

extern int qdev_hotplug;

char *qdev_get_dev_path(DeviceState *dev);

#endif
