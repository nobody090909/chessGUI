from __future__ import annotations
import math
import chess

class SimpleAI:
    """Tiny negamax + alpha-beta with a basic evaluation. For offline fallback only."""
    PIECE_VAL = {
        chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 330,
        chess.ROOK: 500, chess.QUEEN: 900, chess.KING: 0
    }

    def evaluate(self, board: chess.Board) -> int:
        if board.is_checkmate():
            return -10_000 if board.turn else 10_000
        if board.is_stalemate() or board.is_insufficient_material() or board.can_claim_draw():
            return 0
        score = 0
        for _, piece in board.piece_map().items():
            val = self.PIECE_VAL[piece.piece_type]
            score += val if piece.color == chess.WHITE else -val
        # small mobility term
        mob = len(list(board.legal_moves))
        score += (mob * 2 if board.turn else -mob * 2)
        if board.is_check():
            score += 15 if board.turn else -15
        return score

    def order_moves(self, board, moves):
        return sorted(moves, key=lambda m: 1 if board.is_capture(m) else 0, reverse=True)

    def search(self, board, depth, alpha, beta):
        if depth == 0 or board.is_game_over():
            return self.evaluate(board)
        best = -math.inf
        for mv in self.order_moves(board, board.legal_moves):
            board.push(mv)
            score = -self.search(board, depth-1, -beta, -alpha)
            board.pop()
            if score > best:
                best = score
            if best > alpha:
                alpha = best
            if alpha >= beta:
                break
        return best

    def best_move(self, board: chess.Board, depth: int = 3):
        best_mv, best_score = None, -math.inf
        alpha, beta = -math.inf, math.inf
        for mv in self.order_moves(board, board.legal_moves):
            board.push(mv)
            score = -self.search(board, depth-1, -beta, -alpha)
            board.pop()
            if score > best_score:
                best_score, best_mv = score, mv
            if best_score > alpha:
                alpha = best_score
        return best_mv
