Order Processing System – Architecture Notes

When an order arrives, two independent workflows start at the same time: one tracks physical fulfilment and the other tracks payment. They progress in parallel and do not wait for each other.

The fulfilment side starts in a "waiting for stock" phase. Once the warehouse confirms availability — only if remaining capacity is above zero — packing begins, and after packing the parcel moves to a shipped phase. The payment side starts as pending and flips to confirmed once the payment provider responds successfully; at that point a receipt email fires automatically.

The order is only marked complete when both sides have each reached their end phase. Neither can close the order alone. The whole process kicks off when the order is created and finishes when both sides are done.
