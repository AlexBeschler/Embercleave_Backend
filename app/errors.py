class NotFoundError(Exception):
    """Raised by service functions when a resource doesn't exist or doesn't
    belong to the calling user. Routers translate this to a 404.
    """
