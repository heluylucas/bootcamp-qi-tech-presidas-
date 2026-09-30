from sqlalchemy import Column, DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import relationship
from models.base import Base
from models import Book, BookStatus


class BookStatusEvent(Base):
    """Uma linha por mudança de status: o histórico do livro.

    O `book.status_id` diz onde o livro está AGORA; esta tabela diz por
    onde ele passou. Ninguém apaga nem altera uma linha daqui — cada
    cadastro e cada transição acrescenta uma, na mesma transação que muda
    o livro (veja o `BookRepository.update_status`).
    """

    __tablename__ = "book_status_event"

    id = Column(Integer, primary_key=True)
    book_id = Column(Integer, ForeignKey(Book.id), nullable=False)
    status_id = Column(Integer, ForeignKey(BookStatus.id), nullable=False)
    event_datetime = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    book = relationship(
        "Book",
        foreign_keys=[book_id],
        back_populates="status_events",
        lazy="selectin",
    )
    status = relationship("BookStatus", foreign_keys=[status_id], lazy="selectin")
