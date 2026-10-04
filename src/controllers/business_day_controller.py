from controllers.base_controller import BaseController
from repositories import BusinessDayRepository


class BusinessDayController(BaseController):
    def __init__(self) -> None:
        super().__init__(__name__)

    def get(self) -> dict:
        # O seed sempre grava a primeira linha (R2), então nunca vem None.
        business_day = BusinessDayRepository.get_current(self.context)
        return {"business_date": business_day.reference_date.isoformat()}
