from random import choices


class UserType(object):
    STUDENT=1
    INSTITUTE=2
    INSTITUTEGROUPADMIN=3
    CHOICES=(
        (STUDENT,"Student"),
        (INSTITUTE,"Institute"),
        (INSTITUTEGROUPADMIN,"Institute group admin")
    )

class ObjectStatus(object):
    DELETED=0
    ACTIVE=1
    CHOICES = (
        (DELETED, "Deleted"),
        (ACTIVE, "Active"),
    )