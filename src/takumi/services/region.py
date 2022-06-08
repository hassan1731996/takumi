from takumi.models import Region
from takumi.services import Service


class RegionService(Service):
    """
    Represents the business model for Region. This isolates the database
    from the application.
    """

    SUBJECT = Region

    @property
    def region(self):
        return self.subject

    # GET
    @staticmethod
    def get_by_id(id):
        return Region.query.get(id)

    @staticmethod
    def get_all_by_ids(ids):
        return Region.query.filter(Region.id.in_(ids)).all()
