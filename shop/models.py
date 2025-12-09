from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator

# Create your models here.
class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100,unique=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = 'Categories'

    def __str__(self):
        return self.name
    

class Product(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200,unique=True)
    category = models.ForeignKey(Category,on_delete=models.CASCADE,related_name='products')
    description = models.TextField()
    price = models.DecimalField(max_digits=10,decimal_places=2) #122.23
    stock = models.PositiveBigIntegerField(default=1)
    available = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    image = models.ImageField(upload_to = 'products/%Y/%m/%d')

    def __str__(self):
        return self.name
    
    def average_rating(self):
        ratings = self.ratings.all()
        if ratings.count()>0:
            return sum([rating.rating for rating in ratings])/ratings.count()
    
class Rating(models.Model):
    product = models.ForeignKey(Product,on_delete=models.CASCADE, related_name='ratings')#product delete hoiye gele ratin gulo delete hoiye jabe
    user = models.ForeignKey(User,on_delete=models.CASCADE)
    rating = models.PositiveSmallIntegerField(validators = [MinValueValidator(1),MaxValueValidator(5)])
    comment = models.TextField()
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('product','user')

    def __str__(self):
        return f'{self.user.username} - {self.product.name} - {self.rating}'
    

class Cart(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now = True)

    def __str__(self):
        return f'Cart for {self.user.username}'
    
    def get_total_price(self):
        items = self.items.all() # specific cart items
        return sum(item.get_cost() for item in items)
    
    def get_total_qty(self):
        qty = self.items.all()
        return sum(qty.quantity for qty in qty)


class CartItem(models.Model):
    cart = models.ForeignKey(Cart,on_delete=models.CASCADE,related_name='items')
    product = models.ForeignKey(Product,on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f'{self.quantity} X {self.product.name}'
    
    def get_cost(self):
        return (self.product.price)*(self.quantity)


    






