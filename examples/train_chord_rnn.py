from __future__ import annotations

import argparse
import sys
from pathlib import Path

import torch
from torch import nn

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from bachbot.ml import BachDataset


class ChordRNN(nn.Module):
    def __init__(self, vocab_size: int, hidden_size: int) -> None:
        super().__init__()
        self.rnn = nn.GRU(input_size=vocab_size, hidden_size=hidden_size, batch_first=True)
        self.output = nn.Linear(hidden_size, vocab_size)

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        encoded, _ = self.rnn(inputs)
        return self.output(encoded)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train a simple RNN over Bachbot chord sequences.")
    parser.add_argument("corpus_root", type=Path, help="Directory containing MusicXML or DCML note files.")
    parser.add_argument("--pattern", default="**/*.musicxml", help="Glob pattern for source files.")
    parser.add_argument("--limit", type=int, default=8, help="Maximum number of files to load.")
    parser.add_argument("--epochs", type=int, default=1, help="Number of training epochs.")
    parser.add_argument("--hidden-size", type=int, default=32, help="Hidden state width.")
    parser.add_argument("--learning-rate", type=float, default=1e-2, help="Optimizer learning rate.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    paths = sorted(args.corpus_root.glob(args.pattern))
    if args.limit:
        paths = paths[: args.limit]
    if not paths:
        raise SystemExit(f"No files matched {args.pattern!r} under {args.corpus_root}")

    torch.manual_seed(0)
    dataset = BachDataset(paths, representation="chord_sequence")
    vocab_size = len(dataset.vocabulary)
    if vocab_size == 0:
        raise SystemExit("Chord vocabulary is empty")

    model = ChordRNN(vocab_size=vocab_size, hidden_size=args.hidden_size)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.learning_rate)
    criterion = nn.CrossEntropyLoss()

    trained_items = 0
    for epoch in range(1, args.epochs + 1):
        total_loss = 0.0
        trained_items = 0
        for sequence in dataset:
            if sequence.shape[0] < 2:
                continue
            inputs = sequence[:-1].unsqueeze(0)
            targets = sequence[1:].argmax(dim=1)
            logits = model(inputs).reshape(-1, vocab_size)
            loss = criterion(logits, targets)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            total_loss += float(loss.item())
            trained_items += 1
        if trained_items == 0:
            raise SystemExit("Not enough chord transitions to train")
        print(
            f"epoch={epoch} loss={total_loss / trained_items:.4f} "
            f"items={trained_items} vocab={vocab_size}"
        )


if __name__ == "__main__":
    main()
